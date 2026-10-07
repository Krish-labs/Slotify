class NotificationWorker:
    def __init__(self):
        pass

    async def send_email(self, to: str, subject: str, body: str) -> dict:
        # TODO: Implement email sending
        return {
            "status": "not_implemented",
            "message": "Email sending not yet implemented",
        }

    async def send_bulk_notifications(self, notifications: list[dict]) -> dict:
        # TODO: Implement bulk notifications
        return {
            "status": "not_implemented",
            "message": "Bulk notification not yet implemented",
        }
