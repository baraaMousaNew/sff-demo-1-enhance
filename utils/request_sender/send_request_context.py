from utils.request_sender.send_request import SendRequest
from utils.request_sender.system_enums import Systems


class SendRequestContext:

    def send_request(self, system: Systems, request_type: SendRequest):
        if system == Systems.NEW_SYSTEM:
            return request_type.send_request_new_system()
        elif system == Systems.OLD_SYSTEM:
            return request_type.send_request_old_system()
        elif system == Systems.DUAL_OLD_SYSTEM:
            return request_type.send_request_dual_old_system()
        elif system == Systems.DUAL_SYSTEMS:
            return request_type.send_request_dual_systems()
        else:
            raise ValueError(f"Invalid system: {system}")

