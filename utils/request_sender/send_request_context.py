import os
import time

import allure

from utils.env_vars import EnvVar
from utils.request_sender.send_request import SendRequest
from utils.request_sender.system_enums import Systems

# Time the previous transaction in the current scenario finished (per pytest worker process).
# Reset by reset_step_delay() at the start of each test case so the delay only applies between
# steps of one scenario, never between test cases.
_last_send_time = None


def reset_step_delay():
    global _last_send_time
    _last_send_time = None


def _get_step_delay():
    try:
        return max(0.0, float(os.environ.get(EnvVar.SOAP_STEP_DELAY, "0") or "0"))
    except ValueError:
        return 0.0


class SendRequestContext:

    def send_request(self, system: Systems, request_type: SendRequest):
        global _last_send_time
        delay = _get_step_delay()
        if delay > 0 and _last_send_time is not None:
            remaining = delay - (time.monotonic() - _last_send_time)
            if remaining > 0:
                with allure.step(f"Wait {remaining:.1f}s before next transaction"):
                    time.sleep(remaining)
        try:
            return self._dispatch(system, request_type)
        finally:
            _last_send_time = time.monotonic()

    def _dispatch(self, system: Systems, request_type: SendRequest):
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
