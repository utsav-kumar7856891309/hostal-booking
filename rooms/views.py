from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from rooms.models import Bed, Room, RoomCategory
from hostels.models import Hostel

@login_required
def room_search(request):
    hostels = Hostel.objects.all()
    categories = RoomCategory.objects.all()

    # Filters
    selected_hostel = request.GET.get('hostel')
    selected_cat = request.GET.get('category')
    selected_status = request.GET.get('status')
    selected_ac = request.GET.get('is_ac')
    search_q = request.GET.get('q', '').strip()

    beds = Bed.objects.select_related('room', 'room__hostel', 'room__category').all()

    # If user is student, default to their gender eligible hostels
    student = getattr(request.user, 'student_profile', None)
    if student:
        beds = beds.filter(room__hostel__gender=student.gender)

    if selected_hostel:
        beds = beds.filter(room__hostel__code=selected_hostel)
    if selected_cat:
        beds = beds.filter(room__category_id=selected_cat)
    if selected_status:
        beds = beds.filter(status=selected_status)
    if selected_ac:
        is_ac_val = (selected_ac == '1')
        beds = beds.filter(room__category__is_ac=is_ac_val)
    if search_q:
        beds = beds.filter(room__room_number__icontains=search_q)

    beds_count = beds.count()
    beds = beds[:100]  # Limit to 100 for responsive rendering

    context = {
        'hostels': hostels,
        'categories': categories,
        'beds': beds,
        'beds_count': beds_count,
        'student': student,
        'selected_hostel': selected_hostel,
        'selected_cat': selected_cat,
        'selected_status': selected_status,
        'selected_ac': selected_ac,
        'search_q': search_q,
    }
    return render(request, 'rooms/search.html', context)
