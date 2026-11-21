from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from facilities.models import Facility

@login_required
def facilities_index(request):
    facilities = Facility.objects.filter(is_active=True)
    return render(request, 'facilities/index.html', {'facilities': facilities})
