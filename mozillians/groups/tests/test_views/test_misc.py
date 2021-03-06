from django.core.urlresolvers import reverse
from django.test.client import Client

from mock import patch
from nose.tools import eq_, ok_

from mozillians.common.tests import TestCase, requires_login, requires_vouch
from mozillians.groups.models import Group, GroupMembership, Skill
from mozillians.groups.tests import (GroupFactory, SkillFactory)
from mozillians.users.tests import UserFactory


class ToggleGroupSubscriptionTests(TestCase):
    def setUp(self):
        self.group = GroupFactory.create()
        self.user = UserFactory.create()
        # We must request the full path, with language, or the
        # LanguageMiddleware will convert the request to GET.
        self.join_url = reverse('groups:join_group', prefix='/en-US/',
                                kwargs={'url': self.group.url})
        self.leave_url = reverse('groups:remove_member', prefix='/en-US/',
                                 kwargs={'url': self.group.url,
                                         'user_pk': self.user.userprofile.pk})

    @patch('mozillians.groups.models.update_basket_task.delay')
    def test_group_subscription(self, basket_task_mock):
        with self.login(self.user) as client:
            client.post(self.join_url, follow=True)
        group = Group.objects.get(id=self.group.id)
        ok_(group.members.filter(id=self.user.userprofile.id).exists())
        basket_task_mock.assert_called_with(self.user.userprofile.id)

    @patch('mozillians.groups.models.update_basket_task.delay')
    def test_group_subscription_terms(self, basket_task_mock):
        group = GroupFactory.create(terms='Example terms')
        join_url = reverse('groups:join_group', prefix='/en-US/', kwargs={'url': group.url})
        with self.login(self.user) as client:
            client.post(join_url, follow=True)

        membership = group.groupmembership_set.get(userprofile=self.user.userprofile)
        eq_(membership.status, GroupMembership.PENDING_TERMS)
        basket_task_mock.assert_called_with(self.user.userprofile.id)

    @patch('mozillians.groups.models.update_basket_task.delay')
    def test_group_subscription_terms_by_request(self, basket_task_mock):
        group = GroupFactory.create(accepting_new_members='by_request', terms='Example terms')
        join_url = reverse('groups:join_group', prefix='/en-US/', kwargs={'url': group.url})
        with self.login(self.user) as client:
            client.post(join_url, follow=True)

        membership = group.groupmembership_set.get(userprofile=self.user.userprofile)
        eq_(membership.status, GroupMembership.PENDING)
        basket_task_mock.assert_called_with(self.user.userprofile.id)

    @patch('mozillians.groups.models.update_basket_task.delay')
    def test_group_unsubscription(self, basket_task_mock):
        self.group.add_member(self.user.userprofile)
        with self.login(self.user) as client:
            client.post(self.leave_url, follow=True)
        group = Group.objects.get(id=self.group.id)
        ok_(not group.members.filter(id=self.user.userprofile.id).exists())
        basket_task_mock.assert_called_with(self.user.userprofile.id)

    def test_nonexistant_group(self):
        url = reverse('groups:join_group', prefix='/en-US/',
                      kwargs={'url': 'woohoo'})
        with self.login(self.user) as client:
            response = client.post(url, follow=True)
        eq_(response.status_code, 404)

    @requires_vouch()
    def test_unvouched(self):
        user = UserFactory.create(vouched=False)
        join_url = reverse('groups:join_group', prefix='/en-US/',
                           kwargs={'url': self.group.url})
        with self.login(user) as client:
            client.post(join_url, follow=True)

    @requires_login()
    def test_anonymous(self):
        client = Client()
        client.post(self.join_url, follow=True)

    def test_unjoinable_group(self):
        group = GroupFactory.create(accepting_new_members='no')
        join_url = reverse('groups:join_group', prefix='/en-US/',
                           kwargs={'url': group.url})
        with self.login(self.user) as client:
            client.post(join_url, follow=True)
        group = Group.objects.get(id=group.id)
        ok_(not group.members.filter(pk=self.user.pk).exists())


class ToggleSkillSubscriptionTests(TestCase):
    def setUp(self):
        self.skill = SkillFactory.create()
        # We must request the full path, with language, or the
        # LanguageMiddleware will convert the request to GET.
        self.url = reverse('groups:toggle_skill_subscription', prefix='/en-US/',
                           kwargs={'url': self.skill.url})
        self.user = UserFactory.create()

    def test_skill_subscription(self):
        with self.login(self.user) as client:
            client.post(self.url, follow=True)
        skill = Skill.objects.get(id=self.skill.id)
        ok_(skill.members.filter(id=self.user.userprofile.id).exists())

    def test_skill_unsubscription(self):
        self.skill.members.add(self.user.userprofile)
        with self.login(self.user) as client:
            client.post(self.url, follow=True)
        skill = Skill.objects.get(id=self.skill.id)
        ok_(not skill.members.filter(id=self.user.userprofile.id).exists())

    def test_nonexistant_skill(self):
        url = reverse('groups:toggle_skill_subscription', prefix='/en-US/',
                      kwargs={'url': 'invalid'})
        with self.login(self.user) as client:
            response = client.post(url, follow=True)
        eq_(response.status_code, 404)

    def test_get(self):
        url = reverse('groups:toggle_skill_subscription',
                      kwargs={'url': self.skill.url})
        with self.login(self.user) as client:
            response = client.get(url, follow=True)
        eq_(response.status_code, 405)

    @requires_vouch()
    def test_unvouched(self):
        user = UserFactory.create(vouched=False)
        with self.login(user) as client:
            client.post(self.url, follow=True)

    @requires_login()
    def test_anonymous(self):
        client = Client()
        client.post(self.url, follow=True)
