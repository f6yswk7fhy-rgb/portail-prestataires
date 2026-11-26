from .roles import Role, roles_de


def roles(request):
    r = roles_de(getattr(request, "user", None)) if hasattr(request, "user") else set()
    return {"mes_roles": r, "peut_auditer": bool(r & {Role.RSSI, Role.DSI})}
