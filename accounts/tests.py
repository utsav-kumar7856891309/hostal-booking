from django.test import TestCase, Client
from django.contrib.auth import get_user_model

from hostels.models import University, Hostel, Warden
from rooms.models import RoomCategory, Room, Bed
from students.models import Student

User = get_user_model()


class LoginAndDayScholarEligibilityTests(TestCase):
    def setUp(self):
        self.univ = University.objects.create(
            name='Test University',
            code='TUNIV',
            address='Campus Area',
            contact_email='admin@tuniv.edu',
            contact_phone='1234567890'
        )
        self.hostel = Hostel.objects.create(
            name='Boys Hostel A',
            code='H001',
            gender='Male',
            university=self.univ
        )
        self.cat = RoomCategory.objects.create(name='AC Single', is_ac=True, capacity=1)
        self.room = Room.objects.create(hostel=self.hostel, room_number='101', floor=1, category=self.cat)
        self.bed = Bed.objects.create(room=self.room, bed_identifier='B1', status='VACANT')

        self.warden_user = User.objects.create_user(
            username='warden_ha',
            email='warden_ha@anit.edu.in',
            password='HostelX@2026',
            role=User.Role.WARDEN,
            is_staff=True
        )
        self.warden = Warden.objects.create(user=self.warden_user, hostel=self.hostel, is_chief=False)

        self.day_scholar_user = User.objects.create_user(
            username='12313714',
            email='12313714@student.university.edu',
            password='HostelX@2026',
            role=User.Role.STUDENT
        )
        self.day_scholar = Student.objects.create(
            user=self.day_scholar_user,
            student_id='STU_12313714',
            registration_number='12313714',
            full_name='Aarav Sharma',
            email='12313714@student.university.edu',
            mobile_number='+91-9876513714',
            gender='Male',
            student_type='DAY_SCHOLAR',
            course='B.Tech Computer Science',
            department='Engineering',
            academic_year='2nd Year',
            current_bed=None
        )
        self.client = Client()

    def test_login_page_uses_valid_warden_demo_credential(self):
        res = self.client.get('/accounts/login/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "warden_ha")
        self.assertNotContains(res, "warden_boys_a")

    def test_warden_login_and_dashboard_access(self):
        res = self.client.post('/accounts/login/', {
            'username': 'WARDEN_HA',
            'password': 'HostelX@2026',
            'portal': 'hostel_booking'
        }, follow=True)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.redirect_chain[-1][0], '/dashboard/warden/')
        self.assertContains(res, 'Boys Hostel A')

    def test_day_scholar_login_warning_and_booking_block(self):
        res = self.client.post('/accounts/login/', {
            'username': '12313714',
            'password': 'HostelX@2026',
            'portal': 'hostel_booking'
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Day Scholar is not eligible for hostel booking.')

        self.client.force_login(self.day_scholar_user)
        dash_res = self.client.get('/dashboard/student/')
        self.assertEqual(dash_res.status_code, 200)
        self.assertContains(dash_res, 'Day Scholar is not eligible for hostel room booking.')
        self.assertNotContains(dash_res, 'Eligible to book a hostel room')

        detail_res = self.client.get(f'/rooms/book/{self.bed.id}/', follow=True)
        self.assertEqual(detail_res.redirect_chain[-1][0], '/dashboard/student/')
        self.assertContains(detail_res, 'Day Scholar is not eligible for hostel room booking.')

        confirm_res = self.client.post(f'/rooms/book/{self.bed.id}/confirm/', follow=True)
        self.assertEqual(confirm_res.redirect_chain[-1][0], '/dashboard/student/')
        self.bed.refresh_from_db()
        self.assertEqual(self.bed.status, 'VACANT')

