from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from mess.models import MessMenu, MessRegistration, ServiceFeedback

@login_required
def mess_index(request):
    user = request.user
    student = getattr(user, 'student_profile', None)

    # Days
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    today_day = timezone.now().strftime('%A')
    active_day = request.GET.get('day', today_day)

    menus = MessMenu.objects.filter(day_of_week=active_day)

    mess_reg = None
    if student:
        mess_reg = MessRegistration.objects.filter(student=student, is_active=True).first()

    # Update dietary preference
    if request.method == 'POST' and 'update_diet' in request.POST:
        if not student:
            messages.error(request, "Only students can update dietary preference.")
            return redirect('mess_index')

        new_diet = request.POST.get('dietary_preference')
        if mess_reg:
            mess_reg.dietary_preference = new_diet
            mess_reg.save()
            messages.success(request, f"Dietary preference updated to {mess_reg.get_dietary_preference_display()}.")
        return redirect('mess_index')

    # Submit feedback
    if request.method == 'POST' and 'submit_feedback' in request.POST:
        if not student:
            messages.error(request, "Only students can submit feedback.")
            return redirect('mess_index')

        rating = int(request.POST.get('rating', 5))
        title = request.POST.get('title', '')
        comments = request.POST.get('comments', '')

        ServiceFeedback.objects.create(
            student=student,
            service_type='MESS',
            rating=rating,
            title=title,
            comments=comments
        )
        messages.success(request, "Thank you! Your mess feedback has been recorded.")
        return redirect('mess_index')

    feedbacks = ServiceFeedback.objects.filter(service_type='MESS').order_by('-created_at')[:10]

    context = {
        'days': days,
        'active_day': active_day,
        'today_day': today_day,
        'menus': menus,
        'student': student,
        'mess_reg': mess_reg,
        'feedbacks': feedbacks,
    }
    return render(request, 'mess/index.html', context)
