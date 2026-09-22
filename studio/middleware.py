"""Remembers, in cookies, two things the studio kept forgetting between pages.

- The selected language (``?lang=`` or a posted ``language``): leaving the frame editor used to
  drop back to the base language, which is maddening when translating frame 80 in Afrikaans.
- Where editing started (``?from=develop`` or ``?from=flowchart``): the frame editor's
  "Save and exit" and its back link return there, to the frame that was being edited.

A cookie instead of threading the values through every link and form: any page that does name
them (``?lang=en-US``) still wins, because the views read the request first and the cookie second.
"""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

LANGUAGE_COOKIE: str = "tiltale_studio_lang"
ORIGIN_COOKIE: str = "tiltale_studio_origin"
ORIGINS: tuple[str, ...] = ("develop", "flowchart")


class RememberChoicesMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        response: HttpResponse = self.get_response(request)
        language: str = request.GET.get("lang", "") or request.POST.get("language", "")
        if language and language != request.COOKIES.get(LANGUAGE_COOKIE):
            response.set_cookie(LANGUAGE_COOKIE, language, samesite="Lax")
        origin: str = request.GET.get("from", "")
        if origin in ORIGINS and origin != request.COOKIES.get(ORIGIN_COOKIE):
            response.set_cookie(ORIGIN_COOKIE, origin, samesite="Lax")
        return response
