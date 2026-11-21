from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from maintenance.models import MaintenanceRequest

@login_required
def maintenance_index(request):
    user = request.user
    student = getattr(user, 'student_profile', None)

    if student:
        complaints = MaintenanceRequest.objects.filter(student=student).order_by('-created_at')
    else:
        # Wardens/Admin view all
        complaints = MaintenanceRequest.objects.all().order_by('-created_at')[:50]

    if request.method == 'POST' and 'report_issue' in request.POST:
        if not student or not student.current_room or not student.current_hostel:
            messages.error(request, "Active room allocation required to report a maintenance issue.")
            return redirect('maintenance_index')

        category = request.POST.get('category')
        title = request.POST.get('title')
        description = request.POST.get('description')
        priority = request.POST.get('priority', 'MEDIUM')
        image = request.FILES.get('photograph')

        code = f"MNT-{timezone.now().strftime('%Y%m%d%H%M%S')}-{student.id}"

        MaintenanceRequest.objects.create(
            complaint_id=code,
            student=student,
            hostel=student.current_hostel,
            room=student.current_room,
            category=category,
            title=title,
            description=description,
            priority=priority,
            photograph=image,
            status='REPORTED'
        )
        messages.success(request, f"Maintenance ticket #{code} logged successfully! Staff will be dispatched.")
        return redirect('maintenance_index')

    context = {
        'complaints': complaints,
        'student': student,
        'categories': MaintenanceRequest.CATEGORY_CHOICES,
        'priorities': MaintenanceRequest.PRIORITY_CHOICES,
    }
    return render(request, 'maintenance/index.html', context)
