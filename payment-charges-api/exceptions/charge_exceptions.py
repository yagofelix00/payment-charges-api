class ChargeError(Exception):
    pass


class ChargeNotFound(ChargeError):
    pass


class ChargeNotPayable(ChargeError):
    pass


class InvalidChargeValue(ChargeError):
    pass
