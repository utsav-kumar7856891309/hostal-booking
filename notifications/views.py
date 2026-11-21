from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from notifications.models import Notification

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
