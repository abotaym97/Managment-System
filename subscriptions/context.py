from django.utils import translation
from django.http import HttpResponseRedirect


def interface(request):
    language = getattr(request, 'LANGUAGE_CODE', 'en')
    return {'interface_language': language, 'ar': language == 'ar'}


class InterfaceLanguage:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        language = request.GET.get('lang')
        if language in ('en', 'ar'):
            request.session['interface_language'] = language
        if language in ('en', 'ar') and request.path.startswith('/admin/') and request.path != '/admin/login/':
            query = request.GET.copy()
            del query['lang']
            return HttpResponseRedirect(request.path + ('?' + query.urlencode() if query else ''))
        language = request.session.get('interface_language', 'en')
        request.LANGUAGE_CODE = language
        with translation.override(language):
            return self.get_response(request)

