from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from hostels.models import University, Hostel
from rooms.models import RoomCategory, Room, Bed, RoomPricing
from students.models import Student
from allocations.models import BedAllocation, RoomBooking
from finance.models import StudentAccount

User = get_user_model()

class DirectBookingAndAdminTests(TestCase):
    def setUp(self):
        self.univ = University.objects.create(
            name='Test University',
            code='TUNIV',
            address='Campus Area',
            contact_email='admin@tuniv.edu',
            contact_phone='1234567890'
        )
        self.hostel_boys = Hostel.objects.create(name='Boys Block A', code='BHA', gender='Male', university=self.univ)
        self.hostel_girls = Hostel.objects.create(name='Girls Block A', code='GHA', gender='Female', university=self.univ)

        self.cat_single = RoomCategory.objects.create(name='AC Single Test', is_ac=True, capacity=1)
        self.cat_double = RoomCategory.objects.create(name='Non-AC Double Test', is_ac=False, capacity=2)

        RoomPricing.objects.create(hostel=self.hostel_boys, category=self.cat_single, academic_year='2026-2027', annual_fee=Decimal('90000.00'))
        RoomPricing.objects.create(hostel=self.hostel_boys, category=self.cat_double, academic_year='2026-2027', annual_fee=Decimal('60000.00'))

        self.room1 = Room.objects.create(hostel=self.hostel_boys, room_number='101', floor=1, category=self.cat_single)
        self.bed1 = Bed.objects.create(room=self.room1, bed_identifier='B1', status='VACANT')

        self.admin_user = User.objects.create_superuser(username='test_admin_user', email='admin@test.com', password='adminpassword')
        self.admin_user.role = User.Role.ADMIN
        self.admin_user.save()

        self.client = Client()

    def test_student_registration_and_login(self):
        # 1. Verify public registration is disabled and redirects to login
        reg_response = self.client.get('/accounts/register/')
        self.assertEqual(reg_response.status_code, 302)
        self.assertEqual(reg_response.url, '/accounts/login/')

        # 2. Create pre-enrolled Central University Day Scholar student
        user = User.objects.create_user(username='12313714', password='testpassword123', role=User.Role.STUDENT)
        student = Student.objects.create(
            user=user,
            student_id='STU_12313714',
            registration_number='12313714',
            full_name='Aarav Sharma',
            email='aarav@test.com',
            mobile_number='9876543210',
            gender='Male',
            student_type='DAY_SCHOLAR',
            course='B.Tech Computer Science',
            academic_year='2nd Year',
            current_bed=None
        )
        StudentAccount.objects.create(student=student)

        # 3. Test logging in with Registration Number (portal=hostel_booking)
        login_res = self.client.post('/accounts/login/', {
            'username': '12313714',
            'password': 'testpassword123',
            'portal': 'hostel_booking'
        })
        self.assertEqual(login_res.status_code, 302)
        self.assertEqual(login_res.url, '/dashboard/student/')

    def test_admin_control_hub_and_manual_allotment(self):
        self.client.force_login(self.admin_user)

        # 1. Admin Overview
        res = self.client.get('/admin-panel/')
        self.assertEqual(res.status_code, 200)

        # 2. Admin adds a new room
        add_room_res = self.client.post('/admin-panel/rooms/add/', {
            'hostel_id': self.hostel_boys.id,
            'room_number': '305',
            'floor': 3,
            'category_id': self.cat_double.id,
        })
        self.assertEqual(add_room_res.status_code, 302)
        new_room = Room.objects.get(hostel=self.hostel_boys, room_number='305')
        self.assertEqual(new_room.beds.count(), 2) # Capacity was 2

        # 3. Admin changes bed status
        new_bed = new_room.beds.first()
        status_res = self.client.post(f'/admin-panel/beds/{new_bed.id}/status/', {
            'status': 'MAINTENANCE'
        })
        self.assertEqual(status_res.status_code, 302)
        new_bed.refresh_from_db()
        self.assertEqual(new_bed.status, 'MAINTENANCE')

        # 4. Admin manual allotment of an unallocated student
        u = User.objects.create_user(username='unalloc_stu', password='password123', role=User.Role.STUDENT)
        stu = Student.objects.create(
            user=u,
            student_id='STU_UNALLOC',
            registration_number='REG_UNALLOC',
            full_name='Unallocated Student',
            gender='Male',
            course='MBA'
        )
        StudentAccount.objects.create(student=stu)

        vacant_bed = new_room.beds.last()
        vacant_bed.status = 'VACANT'
        vacant_bed.save()

        allot_res = self.client.post('/admin-panel/bookings/manual-allot/', {
            'student_id': stu.id,
            'bed_id': vacant_bed.id
        })
        self.assertEqual(allot_res.status_code, 302)

        stu.refresh_from_db()
        self.assertEqual(stu.current_bed_id, vacant_bed.id)
        vacant_bed.refresh_from_db()
        self.assertEqual(vacant_bed.status, 'OCCUPIED')

        # 5. Admin updates student status (disciplinary hold & unpaid fee)
        hold_res = self.client.post(f'/admin-panel/students/{stu.id}/update-status/', {
            'action': 'disciplinary_status',
            'value': 'HOLD'
        })
        self.assertEqual(hold_res.status_code, 302)
        stu.refresh_from_db()
        self.assertEqual(stu.disciplinary_status, 'HOLD')
