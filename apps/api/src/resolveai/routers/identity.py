from typing import Annotated

from fastapi import APIRouter, Depends

from resolveai.dependencies import RequestContext, get_request_context
from resolveai.schemas import PrincipalResponse

router = APIRouter(prefix="/v1", tags=["identity"])
RequestContextDependency = Annotated[RequestContext, Depends(get_request_context)]


@router.get("/me", response_model=PrincipalResponse)
def me(context: RequestContextDependency) -> PrincipalResponse:
    principal = context.principal
    return PrincipalResponse(
        user_id=principal.user_id,
        tenant_id=principal.tenant_id,
        subject=principal.subject,
        roles=sorted(principal.roles),
        permissions=sorted(principal.permissions),
        customer_id=principal.customer_id,
    )
