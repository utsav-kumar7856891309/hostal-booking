from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from accounts.views import login_view, register_view, logout_view, dashboard_redirect, user_profile
from students.views import student_dashboard, create_exchange_request, propose_direct_exchange
from hostels.views import warden_dashboard, chief_warden_dashboard, admin_dashboard
from hostels.admin_views import (
    admin_panel_overview, admin_rooms_manager, admin_add_room,
    admin_update_bed_status, admin_bookings_manager, admin_manual_allot,
    admin_students_manager, admin_update_student_status
)
from reports.views import dean_dashboard, reports_index
from exchanges.views import (
    proposal_detail, accept_proposal, decline_proposal,
    execute_proposal_now, find_matches
)
from approvals.views import approval_detail
from finance.views import (
    financial_settle_view, my_financial_account,
    download_transfer_letter_pdf, view_transfer_letter_html
)
from allocations.views import (
    room_booking_catalog, room_booking_detail, room_booking_confirm,
    booking_receipt, my_bookings_list
)
from rooms.views import room_search
from mess.views import mess_index
from laundry.views import laundry_index
from maintenance.views import maintenance_index
from facilities.views import facilities_index
from notifications.views import notifications_index, mark_read

urlpatterns = [
    path('admin/', admin.site.urls),

    # Authentication & Registration
    path('', dashboard_redirect, name='index'),
    path('accounts/login/', login_view, name='login'),
    path('accounts/register/', register_view, name='register'),
    path('accounts/logout/', logout_view, name='logout'),
    path('accounts/profile/', user_profile, name='user_profile'),
    path('dashboard/', dashboard_redirect, name='dashboard_redirect'),

    # Direct Room Booking Facility
    path('rooms/book/', room_booking_catalog, name='room_booking_catalog'),
    path('rooms/book/<int:bed_id>/', room_booking_detail, name='room_booking_detail'),
    path('rooms/book/<int:bed_id>/confirm/', room_booking_confirm, name='room_booking_confirm'),
    path('bookings/<int:booking_id>/', booking_receipt, name='booking_receipt'),
    path('my-bookings/', my_bookings_list, name='my_bookings'),

    # Admin Control Panel Hub (Control All The Stuff)
    path('admin-panel/', admin_panel_overview, name='admin_overview'),
    path('admin-panel/rooms/', admin_rooms_manager, name='admin_rooms_manager'),
    path('admin-panel/rooms/add/', admin_add_room, name='admin_add_room'),
    path('admin-panel/beds/<int:bed_id>/status/', admin_update_bed_status, name='admin_update_bed_status'),
    path('admin-panel/bookings/', admin_bookings_manager, name='admin_bookings_manager'),
    path('admin-panel/bookings/manual-allot/', admin_manual_allot, name='admin_manual_allot'),
    path('admin-panel/students/', admin_students_manager, name='admin_students_manager'),
    path('admin-panel/students/<int:student_id>/update-status/', admin_update_student_status, name='admin_update_student_status'),

    # Dashboards
    path('dashboard/student/', student_dashboard, name='student_dashboard'),
    path('dashboard/warden/', warden_dashboard, name='warden_dashboard'),
    path('dashboard/chief-warden/', chief_warden_dashboard, name='chief_warden_dashboard'),
    path('dashboard/admin/', admin_dashboard, name='admin_dashboard'),
    path('dashboard/dean/', dean_dashboard, name='dean_dashboard'),

    # Exchanges & Matching
    path('exchanges/create/', create_exchange_request, name='create_exchange_request'),
    path('exchanges/propose-direct/', propose_direct_exchange, name='propose_direct_exchange'),
    path('exchanges/proposals/<int:proposal_id>/', proposal_detail, name='proposal_detail'),
    path('exchanges/proposals/<int:proposal_id>/accept/', accept_proposal, name='accept_proposal'),
    path('exchanges/proposals/<int:proposal_id>/decline/', decline_proposal, name='decline_proposal'),
    path('exchanges/proposals/<int:proposal_id>/execute/', execute_proposal_now, name='execute_proposal_now'),
    path('exchanges/find-matches/', find_matches, name='find_matches'),

    # Approvals
    path('approvals/detail/<int:proposal_id>/', approval_detail, name='approval_detail'),

    # Finance & Transfer Records
    path('finance/settle/<int:proposal_id>/', financial_settle_view, name='financial_settle'),
    path('finance/my-account/', my_financial_account, name='my_financial_account'),
    path('finance/transfer-letter/<int:record_id>/pdf/', download_transfer_letter_pdf, name='download_transfer_letter_pdf'),
    path('finance/transfer-letter/<int:record_id>/', view_transfer_letter_html, name='view_transfer_letter_html'),

    # Rooms & Beds Explorer
    path('rooms/search/', room_search, name='room_search'),

    # Hostel Services
    path('mess/', mess_index, name='mess_index'),
    path('laundry/', laundry_index, name='laundry_index'),
    path('maintenance/', maintenance_index, name='maintenance_index'),
    path('facilities/', facilities_index, name='facilities_index'),

    # Notifications & Reports
    path('notifications/', notifications_index, name='notifications_index'),
    path('notifications/<int:notif_id>/read/', mark_read, name='mark_read'),
    path('reports/', reports_index, name='reports_index'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
