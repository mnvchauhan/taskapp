# Programmatic Integration Test for Alpha Research Server
import os
import sys
import unittest
import json

# Add workspace directory to python path
sys.path.append('/Users/manav/Desktop/rakesh')

from app import app, db, User, Survey, SurveyResponse, Transaction

class TestAttaPollClone(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        
        # Initialize and seed DB using main default config connection
        with app.app_context():
            db.drop_all() # Reset for clean testing
            db.create_all()
            from app import seed_surveys
            seed_surveys()

    def tearDown(self):
        with app.app_context():
            db.drop_all()
            db.session.remove()

    def test_auth_and_survey_flow(self):
        # 1. Test register user (without referral)
        res = self.client.post('/login', data={
            'action': 'register',
            'username': 'tester_pro',
            'email': 'tester@test.com',
            'password': 'Password123',
            'referral_code': ''
        }, follow_redirects=True)
        
        self.assertEqual(res.status_code, 200)
        html_content = res.data.decode('utf-8')
        self.assertIn('Welcome to Alpha Research Server', html_content)
        
        # Verify user database entry
        with app.app_context():
            user = User.query.filter_by(email='tester@test.com').first()
            self.assertIsNotNone(user)
            self.assertEqual(user.username, 'tester_pro')
            self.assertEqual(user.balance, 0.0) # No welcome bonus without referral code
            self.assertIsNotNone(user.referral_code)
            
            # Keep referral code for next test
            ref_code_1 = user.referral_code
            print(f"Tester registered successfully with referral code: {ref_code_1}")

        # ⚠️ LOG OUT tester_pro so we can register Bob as a new user!
        self.client.get('/logout', follow_redirects=True)

        # 2. Test registration with referral code
        res_ref = self.client.post('/login', data={
            'action': 'register',
            'username': 'friend_bob',
            'email': 'bob@test.com',
            'password': 'PasswordBob',
            'referral_code': ref_code_1
        }, follow_redirects=True)
        
        self.assertEqual(res_ref.status_code, 200)
        html_bob = res_ref.data.decode('utf-8')
        
        with app.app_context():
            # Bob gets $2 welcome bonus
            bob = User.query.filter_by(email='bob@test.com').first()
            self.assertIsNotNone(bob, "Bob should be registered successfully in the DB!")
            self.assertEqual(bob.balance, 2.0)
            
            # Tester gets $5 referral bonus
            tester = User.query.filter_by(email='tester@test.com').first()
            self.assertEqual(tester.balance, 5.0)
            
            # Verify transaction logged
            tester_txn = Transaction.query.filter_by(user_id=tester.id, type='earnings').first()
            self.assertIsNotNone(tester_txn)
            self.assertEqual(tester_txn.amount, 5.0)
            self.assertEqual(tester_txn.method, 'Referral Bonus')

        # 3. Test Dashboard loading
        # (Bob is already logged in now because he just registered)
        dash_res = self.client.get('/')
        self.assertEqual(dash_res.status_code, 200)
        dash_html = dash_res.data.decode('utf-8')
        self.assertIn('Available Surveys', dash_html)
        self.assertIn('Quick Onboarding Survey', dash_html)

        # 4. Run and submit survey
        # Bob answers the Quick Onboarding Survey (ID: 1)
        survey_submit_res = self.client.post('/survey/1/submit', data={
            'q_q1': 'Male',
            'q_q2': '18-24',
            'q_q3': 'Friend recommendation'
        })
        
        self.assertEqual(survey_submit_res.status_code, 200)
        data = json.loads(survey_submit_res.data.decode('utf-8'))
        self.assertTrue(data['success'])
        self.assertEqual(data['reward'], 5.0)
        self.assertEqual(data['new_balance'], 7.0) # 2 welcome + 5 reward = 7.0

        # 5. Check Bob wallet and progress percentage
        wallet_res = self.client.get('/wallet')
        self.assertEqual(wallet_res.status_code, 200)
        wallet_html = wallet_res.data.decode('utf-8')
        self.assertIn('Available Payout Balance', wallet_html)
        # Current balance is $7, threshold is 50, so progress is (7/50)*100 = 14%
        self.assertIn('14% ($50 required)', wallet_html)

        # 6. Test cashout block when balance < threshold ($50)
        # If Bob attempts to POST a withdrawal, the route redirects and flashes limit error
        cashout_res = self.client.post('/wallet', data={
            'method': 'PayPal',
            'details': 'bob@paypal.com'
        }, follow_redirects=True)
        cashout_html = cashout_res.data.decode('utf-8')
        self.assertIn('Minimum withdrawal limit is $50.00', cashout_html)

if __name__ == '__main__':
    unittest.main()
