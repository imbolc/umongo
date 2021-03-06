import pytest

from umongo import Document, fields, set_gettext, ValidationError, validate
from umongo.i18n import gettext
from umongo.abstract import BaseField

from .fixtures import collection_moke


class TestI18N:
    def teardown_method(self, method):
        # Reset i18n config before each test
        set_gettext(None)

    def test_default_behavior(self):
        msg = BaseField.default_error_messages['unique']
        assert msg == gettext(msg)

    def test_custom_gettext(self):

        def my_gettext(message):
            return 'my_' + message

        set_gettext(my_gettext)
        assert gettext('hello') == 'my_hello'

    def test_document_validation(self):

        class Client(Document):
            phone_number = fields.StrField(validate=validate.Regexp(r'^[0-9 ]+$'))

        def my_gettext(message):
            return message.upper()

        set_gettext(my_gettext)
        with pytest.raises(ValidationError) as exc:
            Client(phone_number='not a phone !')
        assert exc.value.args[0] == {'phone_number': ['STRING DOES NOT MATCH EXPECTED PATTERN.']}
