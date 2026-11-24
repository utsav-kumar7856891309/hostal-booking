from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import get_user_model
from notifications.models import Notification

User = get_user_model()

@login_required
def notifications_index(request):
    notifications = request.user.notifications.all().order_by('-created_at')

    if request.method == 'POST' and 'mark_all_read' in request.POST:
        request.user.notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect('notifications_index')

    return render(request, 'notifications/index.html', {'notifications': notifications})

@login_required
def mark_read(request, notif_id):
    notif = get_object_or_404(Notification, id=notif_id, recipient=request.user)
    notif.is_read = True
    notif.save()
    if notif.link:
        return redirect(notif.link)
    return redirect('notifications_index')

@login_required
def admin_send_message(request):
    """Allow admin/warden to send a message (ANNOUNCEMENT notification) to one or all students."""
    user = request.user
    if not (user.is_admin_user or user.is_superuser or user.is_warden or user.is_chief_warden):
        messages.error(request, "Staff privileges required to send messages.")
        return redirect('dashboard_redirect')

    students = User.objects.filter(role='STUDENT').select_related('student_profile').order_by('first_name')
    warden = getattr(user, 'warden_profile', None)
    if user.is_warden and warden and warden.hostel:
        students = students.filter(student_profile__current_hostel=warden.hostel)

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        recipient_id = request.POST.get('recipient_id', 'all')

        if not title or not body:
            messages.error(request, "Title and message body are required.")
        else:
            if recipient_id == 'all':
                recipients = students
                count = 0
                for u in recipients:
                    Notification.objects.create(
                        recipient=u,
                        title=title,
                        message=body,
                        notification_type='ANNOUNCEMENT',
                    )
                    count += 1
                messages.success(request, f"Message sent to all {count} students.")
            else:
                recipient = get_object_or_404(User, pk=recipient_id)
                Notification.objects.create(
                    recipient=recipient,
                    title=title,
                    message=body,
                    notification_type='ANNOUNCEMENT',
                )
                messages.success(request, f"Message sent to {recipient.get_full_name() or recipient.username}.")
            return redirect('admin_send_message')

    return render(request, 'notifications/admin_send_message.html', {
        'students': students,
    })
