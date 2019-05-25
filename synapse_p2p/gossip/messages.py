from construct import Struct, PascalString, VarInt, CString, Switch, this, Bytes, GreedyRange

network_message = Struct(
    "version" / PascalString(VarInt, "utf8"),
    "client" / PascalString(VarInt, "utf8"),
    "method" / CString("utf8"),
    "payload" / Switch(this.method, {
        "ping": Bytes(0),
        "pong": GreedyRange(Struct(
            "ip" / CString("ascii"),
            "port" / Bytes(2),
        ))
    }),
)
