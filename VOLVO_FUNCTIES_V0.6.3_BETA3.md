# Volvo/Lynk functions v0.6.3-beta.3

Target vehicle: Lynk & Co 01 MY2022.

## Confirmed working on MY2022

- Flash lights
- Lock doors
- Unlock doors
- Honk horn

These remote actions may have a noticeable vehicle/backend delay. A companion dashboard should therefore prevent repeated presses while a command is still being confirmed.

## Still experimental on MY2022

- Window ventilation start/stop
- Sunroof open/close

The current facelift endpoints remain unchanged in beta.3. No speculative legacy fallback is sent automatically. The first goal is to capture the exact Lynk backend acknowledgement/error for these commands so a MY2022-specific fallback can be chosen from evidence rather than guesswork.

## Beta.3 changes

### Safe command diagnostics

Remote command responses are logged at INFO level. HTTP failures log the backend response body at WARNING level. The log path redacts the VIN and token-like values are removed/truncated before logging.

Useful log patterns:

- `Lynk & Co command response:`
- `Lynk & Co API error:`

This should expose whether a failed window/sunroof command is rejected as unsupported, invalid, or due to a vehicle precondition.

### Longer targeted readback

Targeted refresh uses incremental waits of 3, 5, 10 and 12 seconds. Effective checkpoints are approximately +3, +8, +18 and +30 seconds after a command.

### Temporary setup connectivity failures

Temporary `aiohttp`/timeout failures during initial setup now raise `ConfigEntryNotReady`. Home Assistant can retry automatically instead of leaving the integration permanently in `Setup failed` after a short Lynk/Azure/DNS outage.

## Companion behavior (v0.7.0-beta.12)

The companion package/dashboard:

- marks flash, horn, lock and unlock as confirmed MY2022 functions;
- blocks paired door/window/sunroof controls while a command is being confirmed;
- waits up to 30 seconds for the relevant state transition;
- releases the control after timeout;
- shows an approximately 10-second failure state when confirmation was not received;
- keeps windows and sunroof explicitly labelled as MY2022 tests.

## Window/sunroof test procedure

1. Start from a known state (windows fully closed / sunroof closed).
2. Send exactly one command.
3. Wait for the 30-second confirmation window.
4. If it fails, do not repeatedly press the button.
5. Save/upload Home Assistant log lines containing `Lynk & Co command response` or `Lynk & Co API error`.
6. Use the returned backend code/message to decide whether a MY2022-specific command family is required.
