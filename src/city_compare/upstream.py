"""Telling "their service is down" apart from "our code is wrong".

Every network-backed service in this package (geocoding, weather, air quality)
already retries with exponential backoff. What it could not do was report *why*
it eventually gave up: a 502 from Open-Meteo and a malformed rules file both
left the CLI with exit code 1, so nothing downstream — a script, a cron, a CI
job — could react differently to the two.

That is the whole point of this module. A transient upstream failure is not a
defect in this program, and it must not be reported as one; but it must not be
swallowed either, because a comparison computed without weather data is not a
comparison with a gap in it, it is a *different ranking* presented as the same
one. So the run still fails — it just fails with a code that says whose fault
it is.

Exit code 75 is `EX_TEMPFAIL` from BSD sysexits.h: "temporary failure,
indicating something that is not really an error; the user is invited to
retry". It is the conventional answer to exactly this question.
"""

import httpx

#: sysexits.h EX_TEMPFAIL — the upstream service was unavailable, try later.
EX_TEMPFAIL = 75


class UpstreamUnavailable(Exception):
    """Marker mixin: a third-party service was unreachable, not our bug.

    Mixed into the per-service error types so existing handlers that catch
    `WeatherError` keep working unchanged, while a caller that cares can catch
    `UpstreamUnavailable` across all of them.
    """


def is_transient(exc: BaseException) -> bool:
    """True when `exc` means "come back later" rather than "you asked wrong".

    A 4xx other than 429 is deliberately *not* transient: retrying a 400 gets
    the same 400, and treating it as an outage would hide a genuine bug in the
    parameters this package builds.
    """
    if isinstance(exc, httpx.HTTPStatusError):
        code = exc.response.status_code
        return code == 429 or 500 <= code < 600
    # Timeouts, refused connections, DNS failures, a peer hanging up mid-body.
    return isinstance(exc, httpx.TransportError)
