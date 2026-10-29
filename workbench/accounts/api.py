from ninja import Router, Schema


router = Router(tags=["accounts"])


class MeOut(Schema):
    id: int
    short_name: str
    full_name: str
    email: str
    url: str


@router.get("/me/", response=MeOut)
def me(request):
    """The authenticated user"""
    user = request.user
    return {
        "id": user.id,
        "short_name": user.get_short_name(),
        "full_name": user.get_full_name(),
        "email": user.email,
        "url": request.build_absolute_uri("/"),
    }
