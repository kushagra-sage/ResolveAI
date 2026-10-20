import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select

from resolveai.dependencies import RequestContext, get_request_context
from resolveai.models import (
    AgentRun,
    Customer,
    Order,
    Payment,
    Refund,
    Shipment,
    SupportTicket,
    TicketMessage,
)
from resolveai.rbac import AuthorizationError, require_permission
from resolveai.schemas import (
    CustomerResponse,
    CustomerSupportOverviewResponse,
    CustomerSupportSummary,
    OrderResponse,
)

router = APIRouter(prefix="/v1/customers", tags=["customers"])
RequestContextDependency = Annotated[RequestContext, Depends(get_request_context)]


def _authorize(context: RequestContext, permission: str, customer_id: uuid.UUID) -> None:
    try:
        require_permission(context.principal, permission, customer_id=customer_id)
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc


@router.get("", response_model=CustomerSupportOverviewResponse)
def list_customer_support(context: RequestContextDependency) -> CustomerSupportOverviewResponse:
    try:
        require_permission(context.principal, "customer:read")
    except AuthorizationError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden") from exc

    customers = context.session.scalars(select(Customer).order_by(Customer.name)).all()
    order_rows = context.session.execute(
        select(
            Order.customer_id,
            func.count(Order.id).label("order_count"),
            func.coalesce(func.sum(Order.total_minor), 0).label("lifetime_value_minor"),
            func.max(Order.currency).label("currency"),
            func.max(Order.placed_at).label("latest_order_at"),
        ).group_by(Order.customer_id)
    ).all()
    ticket_rows = context.session.execute(
        select(
            SupportTicket.customer_id,
            func.count(SupportTicket.id).label("ticket_count"),
            func.sum(case((SupportTicket.status.in_(("resolved", "closed")), 0), else_=1)).label(
                "open_ticket_count"
            ),
        ).group_by(SupportTicket.customer_id)
    ).all()
    tickets = context.session.scalars(
        select(SupportTicket).order_by(SupportTicket.created_at.desc())
    ).all()

    orders_by_customer = {row.customer_id: row for row in order_rows}
    tickets_by_customer = {row.customer_id: row for row in ticket_rows}
    latest_ticket_by_customer: dict[uuid.UUID, SupportTicket] = {}
    for ticket in tickets:
        latest_ticket_by_customer.setdefault(ticket.customer_id, ticket)

    summaries: list[CustomerSupportSummary] = []
    for customer in customers:
        order_stats = orders_by_customer.get(customer.id)
        ticket_stats = tickets_by_customer.get(customer.id)
        latest_ticket = latest_ticket_by_customer.get(customer.id)
        latest_order_at = order_stats.latest_order_at if order_stats is not None else None
        latest_ticket_at = latest_ticket.updated_at if latest_ticket is not None else None
        activity_candidates = [
            value for value in (latest_order_at, latest_ticket_at) if value is not None
        ]
        summaries.append(
            CustomerSupportSummary(
                id=customer.id,
                external_ref=customer.external_ref,
                email=customer.email,
                name=customer.name,
                locale=customer.locale,
                status=customer.status,
                order_count=int(order_stats.order_count) if order_stats is not None else 0,
                ticket_count=int(ticket_stats.ticket_count) if ticket_stats is not None else 0,
                open_ticket_count=(
                    int(ticket_stats.open_ticket_count) if ticket_stats is not None else 0
                ),
                lifetime_value_minor=(
                    int(order_stats.lifetime_value_minor) if order_stats is not None else 0
                ),
                currency=(order_stats.currency if order_stats is not None else None) or "INR",
                latest_ticket_subject=latest_ticket.subject if latest_ticket is not None else None,
                latest_ticket_status=latest_ticket.status if latest_ticket is not None else None,
                latest_activity_at=max(activity_candidates) if activity_candidates else None,
            )
        )

    return CustomerSupportOverviewResponse(
        customer_count=len(summaries),
        ticket_count=sum(row.ticket_count for row in summaries),
        open_ticket_count=sum(row.open_ticket_count for row in summaries),
        customers=summaries,
    )


@router.get("/{customer_id}/workspace")
def customer_workspace(
    customer_id: uuid.UUID,
    context: RequestContextDependency,
) -> dict[str, object]:
    _authorize(context, "customer:read", customer_id)
    customer = context.session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")
    orders = context.session.scalars(
        select(Order).where(Order.customer_id == customer_id).order_by(Order.placed_at.desc())
    ).all()
    order_ids = [order.id for order in orders]
    tickets = context.session.scalars(
        select(SupportTicket)
        .where(SupportTicket.customer_id == customer_id)
        .order_by(SupportTicket.updated_at.desc())
    ).all()
    ticket_ids = [ticket.id for ticket in tickets]
    payments = (
        context.session.scalars(select(Payment).where(Payment.order_id.in_(order_ids))).all()
        if order_ids
        else []
    )
    shipments = (
        context.session.scalars(select(Shipment).where(Shipment.order_id.in_(order_ids))).all()
        if order_ids
        else []
    )
    refunds = (
        context.session.scalars(select(Refund).where(Refund.order_id.in_(order_ids))).all()
        if order_ids
        else []
    )
    messages = (
        context.session.scalars(
            select(TicketMessage)
            .where(TicketMessage.ticket_id.in_(ticket_ids))
            .order_by(TicketMessage.created_at.desc())
        ).all()
        if ticket_ids
        else []
    )
    runs = context.session.scalars(
        select(AgentRun)
        .where(AgentRun.customer_id == customer_id)
        .order_by(AgentRun.created_at.desc())
    ).all()
    return {
        "customer": {
            "id": str(customer.id),
            "external_ref": customer.external_ref,
            "name": customer.name,
            "email": customer.email,
            "locale": customer.locale,
            "status": customer.status,
        },
        "orders": [
            {
                "id": str(row.id),
                "external_ref": row.external_ref,
                "status": row.status,
                "total_minor": row.total_minor,
                "currency": row.currency,
                "placed_at": row.placed_at.isoformat(),
            }
            for row in orders
        ],
        "payments": [
            {
                "id": str(row.id),
                "order_id": str(row.order_id),
                "provider": row.provider,
                "status": row.status,
                "amount_minor": row.amount_minor,
                "currency": row.currency,
                "method_type": row.method_type,
            }
            for row in payments
        ],
        "shipments": [
            {
                "id": str(row.id),
                "order_id": str(row.order_id),
                "carrier": row.carrier,
                "tracking_number": row.tracking_number,
                "status": row.status,
                "estimated_delivery_at": (
                    row.estimated_delivery_at.isoformat() if row.estimated_delivery_at else None
                ),
            }
            for row in shipments
        ],
        "tickets": [
            {
                "id": str(row.id),
                "external_ref": row.external_ref,
                "subject": row.subject,
                "status": row.status,
                "priority": row.priority,
                "updated_at": row.updated_at.isoformat(),
            }
            for row in tickets
        ],
        "messages": [
            {
                "id": str(row.id),
                "ticket_id": str(row.ticket_id),
                "author_type": row.author_type,
                "direction": row.direction,
                "body": row.body,
                "created_at": row.created_at.isoformat(),
            }
            for row in messages
        ],
        "refunds": [
            {
                "id": str(row.id),
                "order_id": str(row.order_id),
                "status": row.status,
                "amount_minor": row.amount_minor,
                "currency": row.currency,
                "reason_code": row.reason_code,
            }
            for row in refunds
        ],
        "resolution_outcomes": [
            {
                "id": str(row.id),
                "trace_id": row.trace_id,
                "status": row.status,
                "intent": row.intent,
                "risk_level": row.risk_level,
                "created_at": row.created_at.isoformat(),
            }
            for row in runs
        ],
    }


@router.get("/{customer_id}", response_model=CustomerResponse)
def get_customer(
    customer_id: uuid.UUID,
    context: RequestContextDependency,
) -> CustomerResponse:
    _authorize(context, "customer:read", customer_id)
    customer = context.session.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="customer not found")
    return CustomerResponse.model_validate(customer, from_attributes=True)


@router.get("/{customer_id}/orders", response_model=list[OrderResponse])
def list_customer_orders(
    customer_id: uuid.UUID,
    context: RequestContextDependency,
) -> list[OrderResponse]:
    _authorize(context, "order:read", customer_id)
    orders = context.session.scalars(
        select(Order).where(Order.customer_id == customer_id).order_by(Order.placed_at.desc())
    ).all()
    return [OrderResponse.model_validate(order, from_attributes=True) for order in orders]
