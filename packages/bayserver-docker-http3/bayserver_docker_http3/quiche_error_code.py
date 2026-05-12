class QuicheErrorCode:
    """Mirror of croute.error.CrouteError sentinels. The Java port loads
    text descriptions from a properties file; in Python we leave the
    numeric value as the message."""

    @staticmethod
    def get_message(code):
        return f"quiche {code}"
