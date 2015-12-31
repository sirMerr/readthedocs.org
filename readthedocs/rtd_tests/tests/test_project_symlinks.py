import os
from functools import wraps

from mock import patch
from django.test import TestCase
from django_dynamic_fixture import get

from readthedocs.builds.models import Version
from readthedocs.projects.models import Project, Domain
from readthedocs.core.symlink import Symlink


def patched(fn):
    '''Patches calls to run_on_app_servers on instance methods'''

    @wraps(fn)
    def wrapper(self):

        def _collect_commands(cmd):
            self.commands.append(cmd)

        with patch('readthedocs.core.symlink.run', _collect_commands):
            return fn(self)
    return wrapper


class TestSubprojects(TestCase):

    def setUp(self):
        self.project = get(Project, slug='kong')
        self.subproject = get(Project, slug='sub')
        self.symlink = Symlink(self.project)
        self.args = {
            'web_root': self.symlink.WEB_ROOT,
            'subproject_root': self.symlink.SUBPROJECT_ROOT,
        }
        self.commands = []

    @patched
    def test_subproject_normal(self):
        self.project.add_subproject(self.subproject)
        self.symlink.symlink_subprojects()
        self.args['subproject'] = self.subproject.slug
        commands = [
            'ln -nsf {web_root}/{subproject} {subproject_root}/{subproject}',
        ]

        for index, command in enumerate(commands):
            self.assertEqual(self.commands[index], command.format(**self.args))

    @patched
    def test_subproject_alias(self):
        self.project.add_subproject(self.subproject, alias='sweet-alias')
        self.symlink.symlink_subprojects()
        self.args['subproject'] = self.subproject.slug
        self.args['alias'] = 'sweet-alias'
        commands = [
            'ln -nsf {web_root}/{subproject} {subproject_root}/{subproject}',
            'ln -nsf {web_root}/{subproject} {subproject_root}/{alias}',
        ]

        for index, command in enumerate(commands):
            self.assertEqual(self.commands[index], command.format(**self.args))


class TestSymlinkCnames(TestCase):

    def setUp(self):
        self.project = get(Project, slug='kong')
        self.version = get(Version, verbose_name='latest', active=True, project=self.project)
        self.symlink = Symlink(self.project)
        self.args = {
            'cname_root': self.symlink.CNAME_ROOT,
            'project_root': self.symlink.PROJECT_ROOT,
        }
        self.commands = []

    @patched
    def test_symlink_cname(self):
        self.cname = get(Domain, project=self.project, url='http://woot.com', cname=True)
        self.symlink.symlink_cnames()
        self.args['cname'] = self.cname.domain
        commands = [
            'ln -nsf {project_root} {cname_root}/{cname}',
        ]

        for index, command in enumerate(commands):
            self.assertEqual(self.commands[index], command.format(**self.args))


class TestSymlinkTranslations(TestCase):

    commands = []

    def setUp(self):
        self.project = get(Project, slug='kong')
        self.translation = get(Project, slug='pip')
        self.translation.language = 'de'
        self.translation.main_lanuage_project = self.project
        self.project.translations.add(self.translation)
        self.translation.save()
        self.project.save()
        self.symlink = Symlink(self.project)
        get(Version, verbose_name='master', active=True, project=self.project)
        get(Version, verbose_name='master', active=True, project=self.translation)
        self.args = {
            'project_root': self.symlink.PROJECT_ROOT,
            'translation_root': os.path.join(self.symlink.WEB_ROOT, self.translation.slug),
        }
        self.assertIn(self.translation, self.project.translations.all())
        self.commands = []

    @patched
    def test_symlink_basic(self):
        '''Test basic scenario, language english, translation german'''
        self.symlink.symlink_translations()
        commands = [
            'ln -nsf {translation_root}/de {project_root}/de',
        ]

        for command in commands:
            self.assertIsNotNone(
                self.commands.pop(
                    self.commands.index(command.format(**self.args))
                ))

    @patched
    def test_symlink_non_english(self):
        '''Test language german, translation english'''
        # Change the languages, and then clear commands, as project.save calls
        # the symlinking
        self.project.language = 'de'
        self.translation.language = 'en'
        self.project.save()
        self.translation.save()
        self.commands = []

        self.symlink.symlink_translations()
        commands = [
            'ln -nsf {translation_root}/en {project_root}/en',
        ]

        for command in commands:
            self.assertIsNotNone(
                self.commands.pop(
                    self.commands.index(command.format(**self.args))
                ))

    @patched
    def test_symlink_no_english(self):
        '''Test language german, no english

        This should symlink the translation to 'en' even though there is no 'en'
        language in translations or project language
        '''
        # Change the languages, and then clear commands, as project.save calls
        # the symlinking
        self.project.language = 'de'
        version = self.project.translations.first()
        self.project.translations.remove(version)
        self.project.save()
        self.assertNotIn(version, self.project.translations.all())
        self.commands = []

        self.symlink.symlink_translations()
        commands = []

        for command in commands:
            self.assertIsNotNone(
                self.commands.pop(
                    self.commands.index(command.format(**self.args))
                ))


class TestSymlinkSingleVersion(TestCase):

    def setUp(self):
        self.project = get(Project, slug='kong')
        self.version = get(Version, verbose_name='latest', active=True, project=self.project)
        self.symlink = Symlink(self.project)
        self.args = {
            'project_root': self.symlink.PROJECT_ROOT,
            'doc_path': self.project.rtd_build_path(),
        }
        self.commands = []

    @patched
    def test_symlink_single_version(self):
        self.symlink.symlink_single_version()
        commands = [
            'ln -nsf {doc_path}/ {project_root}',
        ]

        for index, command in enumerate(commands):
            self.assertEqual(self.commands[index], command.format(**self.args))


class TestSymlinkVersions(TestCase):

    def setUp(self):
        self.project = get(Project, slug='kong')
        self.stable = get(Version, slug='stable', verbose_name='stable', active=True, project=self.project)
        self.symlink = Symlink(self.project)
        self.args = {
            'project_root': self.symlink.PROJECT_ROOT,
            'latest_path': self.project.rtd_build_path('latest'),
            'stable_path': self.project.rtd_build_path('stable'),
        }
        self.commands = []

    @patched
    def test_symlink_versions(self):
        self.symlink.symlink_versions()
        commands = [
            'ln -nsf {stable_path} {project_root}/en/stable',
            'ln -nsf {latest_path} {project_root}/en/latest',
        ]

        for index, command in enumerate(commands):
            self.assertEqual(self.commands[index], command.format(**self.args))

    @patched
    def test_no_symlink_private_versions(self):
        self.stable.privacy_level = 'private'
        self.stable.save()
        self.symlink.symlink_versions()
        commands = [
            'ln -nsf {latest_path} {project_root}/en/latest',
        ]

        for index, command in enumerate(commands):
            self.assertEqual(self.commands[index], command.format(**self.args))

    def test_removed_versions(self):
        version_link = os.path.join(
            self.symlink.PROJECT_ROOT, 'en', self.stable.slug
            )
        self.symlink.symlink_versions()
        self.assertTrue(os.path.lexists(version_link))
        self.stable.privacy_level = 'private'
        self.stable.save()
        self.symlink.symlink_versions()
        self.assertTrue(not os.path.lexists(version_link))
