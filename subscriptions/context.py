def interface(request):
    language = request.GET.get('lang')
    if language in ('en', 'ar'):
        request.session['interface_language'] = language
    language = request.session.get('interface_language', 'en')
    return {'interface_language': language, 'ar': language == 'ar'}
