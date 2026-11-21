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
        # 1. Register a new student account
        response = self.client.post('/accounts/register/', {
            'username': 'new_student_user',
            'password': 'testpassword123',
            'confirm_password': 'testpassword123',
            'first_name': 'New',
            'last_name': 'Student',
            'email': 'new_student@test.com',
            'phone': '9876543210',
            'gender': 'Male',
            'course': 'B.Tech Computer Science',
            'department': 'CSE',
            'academic_year': '1st Year',
            'admission_year': 2026,
        })
        self.assertEqual(response.status_code, 302) # Redirects to room booking catalog

        # Verify user & student profile created
        user = User.objects.get(username='new_student_user')
        self.assertTrue(user.is_student)
        student = Student.objects.get(user=user)
        self.assertEqual(student.gender, 'Male')
        self.assertIsNone(student.current_bed) # Unallocated initially

        # 2. Test logging out and logging back in
        self.client.logout()
        login_res = self.client.post('/accounts/login/', {
            'username': 'new_student_user',
            'password': 'testpassword123'
        })
        self.assertEqual(login_res.status_code, 302)

    def test_direct_room_booking_flow(self):
        # Register and login student
        user = User.objects.create_user(username='booking_student', password='password123', role=User.Role.STUDENT)
        student = Student.objects.create(
            user=user,
            student_id='STU_BKG_TEST',
            registration_number='REG_BKG_TEST',
            full_name='Booking Tester',
            email='tester@test.com',
            mobile_number='9999999999',
            gender='Male',
            course='B.Tech CS',
            academic_year='2nd Year'
        )
        StudentAccount.objects.create(student=student)
        self.client.force_login(user)

        # 1. View booking catalog
        catalog_res = self.client.get('/rooms/book/')
        self.assertEqual(catalog_res.status_code, 200)
        self.assertContains(catalog_res, self.bed1.full_code)

        # 2. View booking confirmation page
        detail_res = self.client.get(f'/rooms/book/{self.bed1.id}/')
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, '90000')

        # 3. Confirm booking (POST)
        confirm_res = self.client.post(f'/rooms/book/{self.bed1.id}/confirm/')
        self.assertEqual(confirm_res.status_code, 302) # Redirects to receipt

        # 4. Verify DB state
        self.bed1.refresh_from_db()
        self.assertEqual(self.bed1.status, 'OCCUPIED')

        student.refresh_from_db()
        self.assertEqual(student.current_bed_id, self.bed1.id)
        self.assertEqual(student.current_hostel_id, self.hostel_boys.id)

        # Verify RoomBooking record
        booking = RoomBooking.objects.get(student=student, bed=self.bed1)
        self.assertEqual(booking.status, 'CONFIRMED')
        self.assertEqual(booking.annual_fee, Decimal('90000.00'))

        # Verify active BedAllocation
        alloc = BedAllocation.objects.get(student=student, bed=self.bed1, is_active=True)
        self.assertIsNotNone(alloc)

        # 5. View allotment receipt
        receipt_res = self.client.get(f'/bookings/{booking.id}/')
        self.assertEqual(receipt_res.status_code, 200)
        self.assertContains(receipt_res, booking.booking_id)

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
