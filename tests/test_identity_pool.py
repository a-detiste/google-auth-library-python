# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import base64
import datetime
import http.client as http_client
import json
import os
import urllib
from unittest import mock

from OpenSSL import crypto
import pytest  # type: ignore

from google.auth import _helpers, external_account
from google.auth import exceptions
from google.auth import identity_pool
from google.auth import metrics
from google.auth import transport
from google.auth.credentials import DEFAULT_UNIVERSE_DOMAIN

CLIENT_ID = "username"
CLIENT_SECRET = "password"
# Base64 encoding of "username:password".
BASIC_AUTH_ENCODING = "dXNlcm5hbWU6cGFzc3dvcmQ="
SERVICE_ACCOUNT_EMAIL = "service-1234@service-name.iam.gserviceaccount.com"
SERVICE_ACCOUNT_IMPERSONATION_URL_BASE = (
    "https://us-east1-iamcredentials.googleapis.com"
)
SERVICE_ACCOUNT_IMPERSONATION_URL_ROUTE = "/v1/projects/-/serviceAccounts/{}:generateAccessToken".format(
    SERVICE_ACCOUNT_EMAIL
)
SERVICE_ACCOUNT_IMPERSONATION_URL = (
    SERVICE_ACCOUNT_IMPERSONATION_URL_BASE + SERVICE_ACCOUNT_IMPERSONATION_URL_ROUTE
)

QUOTA_PROJECT_ID = "QUOTA_PROJECT_ID"
SCOPES = ["scope1", "scope2"]
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SUBJECT_TOKEN_TEXT_FILE = os.path.join(DATA_DIR, "external_subject_token.txt")
SUBJECT_TOKEN_JSON_FILE = os.path.join(DATA_DIR, "external_subject_token.json")
TRUST_CHAIN_WITH_LEAF_FILE = os.path.join(DATA_DIR, "trust_chain_with_leaf.pem")
TRUST_CHAIN_WITHOUT_LEAF_FILE = os.path.join(DATA_DIR, "trust_chain_without_leaf.pem")
TRUST_CHAIN_WRONG_ORDER_FILE = os.path.join(DATA_DIR, "trust_chain_wrong_order.pem")
CERT_FILE = os.path.join(DATA_DIR, "public_cert.pem")
KEY_FILE = os.path.join(DATA_DIR, "privatekey.pem")
OTHER_CERT_FILE = os.path.join(DATA_DIR, "other_cert.pem")

SUBJECT_TOKEN_FIELD_NAME = "access_token"

with open(SUBJECT_TOKEN_TEXT_FILE) as fh:
    TEXT_FILE_SUBJECT_TOKEN = fh.read()

with open(SUBJECT_TOKEN_JSON_FILE) as fh:
    JSON_FILE_CONTENT = json.load(fh)
    JSON_FILE_SUBJECT_TOKEN = JSON_FILE_CONTENT.get(SUBJECT_TOKEN_FIELD_NAME)

with open(CERT_FILE, "rb") as f:
    CERT_FILE_CONTENT = base64.b64encode(
        crypto.dump_certificate(
            crypto.FILETYPE_ASN1, crypto.load_certificate(crypto.FILETYPE_PEM, f.read())
        )
    ).decode("utf-8")

with open(OTHER_CERT_FILE, "rb") as f:
    OTHER_CERT_FILE_CONTENT = base64.b64encode(
        crypto.dump_certificate(
            crypto.FILETYPE_ASN1, crypto.load_certificate(crypto.FILETYPE_PEM, f.read())
        )
    ).decode("utf-8")

TOKEN_URL = "https://sts.googleapis.com/v1/token"
TOKEN_INFO_URL = "https://sts.googleapis.com/v1/introspect"
SUBJECT_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:jwt"
AUDIENCE = "//iam.googleapis.com/projects/123456/locations/global/workloadIdentityPools/POOL_ID/providers/PROVIDER_ID"
WORKFORCE_AUDIENCE = (
    "//iam.googleapis.com/locations/global/workforcePools/POOL_ID/providers/PROVIDER_ID"
)
WORKFORCE_SUBJECT_TOKEN_TYPE = "urn:ietf:params:oauth:token-type:id_token"
WORKFORCE_POOL_USER_PROJECT = "WORKFORCE_POOL_USER_PROJECT_NUMBER"

VALID_TOKEN_URLS = [
    "https://sts.googleapis.com",
    "https://us-east-1.sts.googleapis.com",
    "https://US-EAST-1.sts.googleapis.com",
    "https://sts.us-east-1.googleapis.com",
    "https://sts.US-WEST-1.googleapis.com",
    "https://us-east-1-sts.googleapis.com",
    "https://US-WEST-1-sts.googleapis.com",
    "https://us-west-1-sts.googleapis.com/path?query",
    "https://sts-us-east-1.p.googleapis.com",
]
INVALID_TOKEN_URLS = [
    "https://iamcredentials.googleapis.com",
    "sts.googleapis.com",
    "https://",
    "http://sts.googleapis.com",
    "https://st.s.googleapis.com",
    "https://us-eas\t-1.sts.googleapis.com",
    "https:/us-east-1.sts.googleapis.com",
    "https://US-WE/ST-1-sts.googleapis.com",
    "https://sts-us-east-1.googleapis.com",
    "https://sts-US-WEST-1.googleapis.com",
    "testhttps://us-east-1.sts.googleapis.com",
    "https://us-east-1.sts.googleapis.comevil.com",
    "https://us-east-1.us-east-1.sts.googleapis.com",
    "https://us-ea.s.t.sts.googleapis.com",
    "https://sts.googleapis.comevil.com",
    "hhttps://us-east-1.sts.googleapis.com",
    "https://us- -1.sts.googleapis.com",
    "https://-sts.googleapis.com",
    "https://us-east-1.sts.googleapis.com.evil.com",
    "https://sts.pgoogleapis.com",
    "https://p.googleapis.com",
    "https://sts.p.com",
    "http://sts.p.googleapis.com",
    "https://xyz-sts.p.googleapis.com",
    "https://sts-xyz.123.p.googleapis.com",
    "https://sts-xyz.p1.googleapis.com",
    "https://sts-xyz.p.foo.com",
    "https://sts-xyz.p.foo.googleapis.com",
]
VALID_SERVICE_ACCOUNT_IMPERSONATION_URLS = [
    "https://iamcredentials.googleapis.com",
    "https://us-east-1.iamcredentials.googleapis.com",
    "https://US-EAST-1.iamcredentials.googleapis.com",
    "https://iamcredentials.us-east-1.googleapis.com",
    "https://iamcredentials.US-WEST-1.googleapis.com",
    "https://us-east-1-iamcredentials.googleapis.com",
    "https://US-WEST-1-iamcredentials.googleapis.com",
    "https://us-west-1-iamcredentials.googleapis.com/path?query",
    "https://iamcredentials-us-east-1.p.googleapis.com",
]
INVALID_SERVICE_ACCOUNT_IMPERSONATION_URLS = [
    "https://sts.googleapis.com",
    "iamcredentials.googleapis.com",
    "https://",
    "http://iamcredentials.googleapis.com",
    "https://iamcre.dentials.googleapis.com",
    "https://us-eas\t-1.iamcredentials.googleapis.com",
    "https:/us-east-1.iamcredentials.googleapis.com",
    "https://US-WE/ST-1-iamcredentials.googleapis.com",
    "https://iamcredentials-us-east-1.googleapis.com",
    "https://iamcredentials-US-WEST-1.googleapis.com",
    "testhttps://us-east-1.iamcredentials.googleapis.com",
    "https://us-east-1.iamcredentials.googleapis.comevil.com",
    "https://us-east-1.us-east-1.iamcredentials.googleapis.com",
    "https://us-ea.s.t.iamcredentials.googleapis.com",
    "https://iamcredentials.googleapis.comevil.com",
    "hhttps://us-east-1.iamcredentials.googleapis.com",
    "https://us- -1.iamcredentials.googleapis.com",
    "https://-iamcredentials.googleapis.com",
    "https://us-east-1.iamcredentials.googleapis.com.evil.com",
    "https://iamcredentials.pgoogleapis.com",
    "https://p.googleapis.com",
    "https://iamcredentials.p.com",
    "http://iamcredentials.p.googleapis.com",
    "https://xyz-iamcredentials.p.googleapis.com",
    "https://iamcredentials-xyz.123.p.googleapis.com",
    "https://iamcredentials-xyz.p1.googleapis.com",
    "https://iamcredentials-xyz.p.foo.com",
    "https://iamcredentials-xyz.p.foo.googleapis.com",
]


class TestSubjectTokenSupplier(identity_pool.SubjectTokenSupplier):
    def __init__(
        self, subject_token=None, subject_token_exception=None, expected_context=None
    ):
        self._subject_token = subject_token
        self._subject_token_exception = subject_token_exception
        self._expected_context = expected_context

    def get_subject_token(self, context, request):
        if self._expected_context is not None:
            assert self._expected_context == context
        if self._subject_token_exception is not None:
            raise self._subject_token_exception
        return self._subject_token


class TestCredentials(object):
    CREDENTIAL_SOURCE_TEXT = {"file": SUBJECT_TOKEN_TEXT_FILE}
    CREDENTIAL_SOURCE_JSON = {
        "file": SUBJECT_TOKEN_JSON_FILE,
        "format": {"type": "json", "subject_token_field_name": "access_token"},
    }
    CREDENTIAL_URL = "http://fakeurl.com"
    CREDENTIAL_SOURCE_TEXT_URL = {"url": CREDENTIAL_URL}
    CREDENTIAL_SOURCE_JSON_URL = {
        "url": CREDENTIAL_URL,
        "format": {"type": "json", "subject_token_field_name": "access_token"},
    }
    CREDENTIAL_SOURCE_CERTIFICATE = {
        "certificate": {"use_default_certificate_config": "true"}
    }
    CREDENTIAL_SOURCE_CERTIFICATE_NOT_DEFAULT = {
        "certificate": {"certificate_config_location": "path/to/config"}
    }
    CREDENTIAL_SOURCE_CERTIFICATE_TRUST_CHAIN_WITH_LEAF = {
        "certificate": {
            "use_default_certificate_config": "true",
            "trust_chain_path": TRUST_CHAIN_WITH_LEAF_FILE,
        }
    }
    CREDENTIAL_SOURCE_CERTIFICATE_TRUST_CHAIN_WITHOUT_LEAF = {
        "certificate": {
            "use_default_certificate_config": "true",
            "trust_chain_path": TRUST_CHAIN_WITHOUT_LEAF_FILE,
        }
    }
    CREDENTIAL_SOURCE_CERTIFICATE_TRUST_CHAIN_WRONG_ORDER = {
        "certificate": {
            "use_default_certificate_config": "true",
            "trust_chain_path": TRUST_CHAIN_WRONG_ORDER_FILE,
        }
    }
    SUCCESS_RESPONSE = {
        "access_token": "ACCESS_TOKEN",
        "issued_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "token_type": "Bearer",
        "expires_in": 3600,
        "scope": " ".join(SCOPES),
    }

    @classmethod
    def make_mock_response(cls, status, data):
        response = mock.create_autospec(transport.Response, instance=True)
        response.status = status
        if isinstance(data, dict):
            response.data = json.dumps(data).encode("utf-8")
        else:
            response.data = data
        return response

    @classmethod
    def make_mock_request(
        cls, token_status=http_client.OK, token_data=None, *extra_requests
    ):
        responses = []
        responses.append(cls.make_mock_response(token_status, token_data))

        while len(extra_requests) > 0:
            # If service account impersonation is requested, mock the expected response.
            status, data, extra_requests = (
                extra_requests[0],
                extra_requests[1],
                extra_requests[2:],
            )
            responses.append(cls.make_mock_response(status, data))

        request = mock.create_autospec(transport.Request)
        request.side_effect = responses

        return request

    @classmethod
    def assert_credential_request_kwargs(
        cls, request_kwargs, headers, url=CREDENTIAL_URL
    ):
        assert request_kwargs["url"] == url
        assert request_kwargs["method"] == "GET"
        assert request_kwargs["headers"] == headers
        assert request_kwargs.get("body", None) is None

    @classmethod
    def assert_token_request_kwargs(
        cls, request_kwargs, headers, request_data, token_url=TOKEN_URL
    ):
        assert request_kwargs["url"] == token_url
        assert request_kwargs["method"] == "POST"
        assert request_kwargs["headers"] == headers
        assert request_kwargs["body"] is not None
        body_tuples = urllib.parse.parse_qsl(request_kwargs["body"])
        assert len(body_tuples) == len(request_data.keys())
        for (k, v) in body_tuples:
            assert v.decode("utf-8") == request_data[k.decode("utf-8")]

    @classmethod
    def assert_impersonation_request_kwargs(
        cls,
        request_kwargs,
        headers,
        request_data,
        service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
    ):
        assert request_kwargs["url"] == service_account_impersonation_url
        assert request_kwargs["method"] == "POST"
        assert request_kwargs["headers"] == headers
        assert request_kwargs["body"] is not None
        body_json = json.loads(request_kwargs["body"].decode("utf-8"))
        assert body_json == request_data

    @classmethod
    def assert_underlying_credentials_refresh(
        cls,
        credentials,
        audience,
        subject_token,
        subject_token_type,
        token_url,
        service_account_impersonation_url=None,
        basic_auth_encoding=None,
        quota_project_id=None,
        used_scopes=None,
        credential_data=None,
        scopes=None,
        default_scopes=None,
        workforce_pool_user_project=None,
    ):
        """Utility to assert that a credentials are initialized with the expected
        attributes by calling refresh functionality and confirming response matches
        expected one and that the underlying requests were populated with the
        expected parameters.
        """
        # STS token exchange request/response.
        token_response = cls.SUCCESS_RESPONSE.copy()
        token_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        if basic_auth_encoding:
            token_headers["Authorization"] = "Basic " + basic_auth_encoding

        metrics_options = {}
        if credentials._service_account_impersonation_url:
            metrics_options["sa-impersonation"] = "true"
        else:
            metrics_options["sa-impersonation"] = "false"
        metrics_options["config-lifetime"] = "false"
        if credentials._credential_source:
            if credentials._credential_source_file:
                metrics_options["source"] = "file"
            else:
                metrics_options["source"] = "url"
        else:
            metrics_options["source"] = "programmatic"

        token_headers["x-goog-api-client"] = metrics.byoid_metrics_header(
            metrics_options
        )

        if service_account_impersonation_url:
            token_scopes = "https://www.googleapis.com/auth/iam"
        else:
            token_scopes = " ".join(used_scopes or [])

        token_request_data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
            "audience": audience,
            "requested_token_type": "urn:ietf:params:oauth:token-type:access_token",
            "scope": token_scopes,
            "subject_token": subject_token,
            "subject_token_type": subject_token_type,
        }
        if workforce_pool_user_project:
            token_request_data["options"] = urllib.parse.quote(
                json.dumps({"userProject": workforce_pool_user_project})
            )

        metrics_header_value = (
            "gl-python/3.7 auth/1.1 auth-request-type/at cred-type/imp"
        )
        if service_account_impersonation_url:
            # Service account impersonation request/response.
            expire_time = (
                _helpers.utcnow().replace(microsecond=0)
                + datetime.timedelta(seconds=3600)
            ).isoformat("T") + "Z"
            impersonation_response = {
                "accessToken": "SA_ACCESS_TOKEN",
                "expireTime": expire_time,
            }
            impersonation_headers = {
                "Content-Type": "application/json",
                "authorization": "Bearer {}".format(token_response["access_token"]),
                "x-goog-api-client": metrics_header_value,
                "x-allowed-locations": "0x0",
            }
            impersonation_request_data = {
                "delegates": None,
                "scope": used_scopes,
                "lifetime": "3600s",
            }

        # Initialize mock request to handle token retrieval, token exchange and
        # service account impersonation request.
        requests = []
        if credential_data:
            requests.append((http_client.OK, credential_data))

        token_request_index = len(requests)
        requests.append((http_client.OK, token_response))

        if service_account_impersonation_url:
            impersonation_request_index = len(requests)
            requests.append((http_client.OK, impersonation_response))

        request = cls.make_mock_request(*[el for req in requests for el in req])

        with mock.patch(
            "google.auth.metrics.token_request_access_token_impersonate",
            return_value=metrics_header_value,
        ):
            credentials.refresh(request)

        assert len(request.call_args_list) == len(requests)
        if credential_data:
            cls.assert_credential_request_kwargs(request.call_args_list[0][1], None)
        # Verify token exchange request parameters.
        cls.assert_token_request_kwargs(
            request.call_args_list[token_request_index][1],
            token_headers,
            token_request_data,
            token_url,
        )
        # Verify service account impersonation request parameters if the request
        # is processed.
        if service_account_impersonation_url:
            cls.assert_impersonation_request_kwargs(
                request.call_args_list[impersonation_request_index][1],
                impersonation_headers,
                impersonation_request_data,
                service_account_impersonation_url,
            )
            assert credentials.token == impersonation_response["accessToken"]
        else:
            assert credentials.token == token_response["access_token"]
        assert credentials.quota_project_id == quota_project_id
        assert credentials.scopes == scopes
        assert credentials.default_scopes == default_scopes

    @classmethod
    def make_credentials(
        cls,
        audience=AUDIENCE,
        subject_token_type=SUBJECT_TOKEN_TYPE,
        token_url=TOKEN_URL,
        token_info_url=TOKEN_INFO_URL,
        client_id=None,
        client_secret=None,
        quota_project_id=None,
        scopes=None,
        default_scopes=None,
        service_account_impersonation_url=None,
        credential_source=None,
        subject_token_supplier=None,
        workforce_pool_user_project=None,
    ):
        return identity_pool.Credentials(
            audience=audience,
            subject_token_type=subject_token_type,
            token_url=token_url,
            token_info_url=token_info_url,
            service_account_impersonation_url=service_account_impersonation_url,
            credential_source=credential_source,
            subject_token_supplier=subject_token_supplier,
            client_id=client_id,
            client_secret=client_secret,
            quota_project_id=quota_project_id,
            scopes=scopes,
            default_scopes=default_scopes,
            workforce_pool_user_project=workforce_pool_user_project,
        )

    @mock.patch.object(identity_pool.Credentials, "__init__", return_value=None)
    def test_from_info_full_options(self, mock_init):
        credentials = identity_pool.Credentials.from_info(
            {
                "audience": AUDIENCE,
                "subject_token_type": SUBJECT_TOKEN_TYPE,
                "token_url": TOKEN_URL,
                "token_info_url": TOKEN_INFO_URL,
                "service_account_impersonation_url": SERVICE_ACCOUNT_IMPERSONATION_URL,
                "service_account_impersonation": {"token_lifetime_seconds": 2800},
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "quota_project_id": QUOTA_PROJECT_ID,
                "credential_source": self.CREDENTIAL_SOURCE_TEXT,
            }
        )

        # Confirm identity_pool.Credentials instantiated with expected attributes.
        assert isinstance(credentials, identity_pool.Credentials)
        mock_init.assert_called_once_with(
            audience=AUDIENCE,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            token_info_url=TOKEN_INFO_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            service_account_impersonation_options={"token_lifetime_seconds": 2800},
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            subject_token_supplier=None,
            quota_project_id=QUOTA_PROJECT_ID,
            workforce_pool_user_project=None,
            universe_domain=DEFAULT_UNIVERSE_DOMAIN,
        )

    @mock.patch.object(identity_pool.Credentials, "__init__", return_value=None)
    def test_from_info_required_options_only(self, mock_init):
        credentials = identity_pool.Credentials.from_info(
            {
                "audience": AUDIENCE,
                "subject_token_type": SUBJECT_TOKEN_TYPE,
                "token_url": TOKEN_URL,
                "credential_source": self.CREDENTIAL_SOURCE_TEXT,
            }
        )

        # Confirm identity_pool.Credentials instantiated with expected attributes.
        assert isinstance(credentials, identity_pool.Credentials)
        mock_init.assert_called_once_with(
            audience=AUDIENCE,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            token_info_url=None,
            service_account_impersonation_url=None,
            service_account_impersonation_options={},
            client_id=None,
            client_secret=None,
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            subject_token_supplier=None,
            quota_project_id=None,
            workforce_pool_user_project=None,
            universe_domain=DEFAULT_UNIVERSE_DOMAIN,
        )

    @mock.patch.object(identity_pool.Credentials, "__init__", return_value=None)
    def test_from_info_supplier(self, mock_init):
        supplier = TestSubjectTokenSupplier()

        credentials = identity_pool.Credentials.from_info(
            {
                "audience": AUDIENCE,
                "subject_token_type": SUBJECT_TOKEN_TYPE,
                "token_url": TOKEN_URL,
                "subject_token_supplier": supplier,
            }
        )

        # Confirm identity_pool.Credentials instantiated with expected attributes.
        assert isinstance(credentials, identity_pool.Credentials)
        mock_init.assert_called_once_with(
            audience=AUDIENCE,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            token_info_url=None,
            service_account_impersonation_url=None,
            service_account_impersonation_options={},
            client_id=None,
            client_secret=None,
            credential_source=None,
            subject_token_supplier=supplier,
            quota_project_id=None,
            workforce_pool_user_project=None,
            universe_domain=DEFAULT_UNIVERSE_DOMAIN,
        )

    @mock.patch.object(identity_pool.Credentials, "__init__", return_value=None)
    def test_from_info_workforce_pool(self, mock_init):
        credentials = identity_pool.Credentials.from_info(
            {
                "audience": WORKFORCE_AUDIENCE,
                "subject_token_type": WORKFORCE_SUBJECT_TOKEN_TYPE,
                "token_url": TOKEN_URL,
                "credential_source": self.CREDENTIAL_SOURCE_TEXT,
                "workforce_pool_user_project": WORKFORCE_POOL_USER_PROJECT,
            }
        )

        # Confirm identity_pool.Credentials instantiated with expected attributes.
        assert isinstance(credentials, identity_pool.Credentials)
        mock_init.assert_called_once_with(
            audience=WORKFORCE_AUDIENCE,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            token_info_url=None,
            service_account_impersonation_url=None,
            service_account_impersonation_options={},
            client_id=None,
            client_secret=None,
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            subject_token_supplier=None,
            quota_project_id=None,
            workforce_pool_user_project=WORKFORCE_POOL_USER_PROJECT,
            universe_domain=DEFAULT_UNIVERSE_DOMAIN,
        )

    @mock.patch.object(identity_pool.Credentials, "__init__", return_value=None)
    def test_from_file_full_options(self, mock_init, tmpdir):
        info = {
            "audience": AUDIENCE,
            "subject_token_type": SUBJECT_TOKEN_TYPE,
            "token_url": TOKEN_URL,
            "token_info_url": TOKEN_INFO_URL,
            "service_account_impersonation_url": SERVICE_ACCOUNT_IMPERSONATION_URL,
            "service_account_impersonation": {"token_lifetime_seconds": 2800},
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "quota_project_id": QUOTA_PROJECT_ID,
            "credential_source": self.CREDENTIAL_SOURCE_TEXT,
        }
        config_file = tmpdir.join("config.json")
        config_file.write(json.dumps(info))
        credentials = identity_pool.Credentials.from_file(str(config_file))

        # Confirm identity_pool.Credentials instantiated with expected attributes.
        assert isinstance(credentials, identity_pool.Credentials)
        mock_init.assert_called_once_with(
            audience=AUDIENCE,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            token_info_url=TOKEN_INFO_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            service_account_impersonation_options={"token_lifetime_seconds": 2800},
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            subject_token_supplier=None,
            quota_project_id=QUOTA_PROJECT_ID,
            workforce_pool_user_project=None,
            universe_domain=DEFAULT_UNIVERSE_DOMAIN,
        )

    @mock.patch.object(identity_pool.Credentials, "__init__", return_value=None)
    def test_from_file_required_options_only(self, mock_init, tmpdir):
        info = {
            "audience": AUDIENCE,
            "subject_token_type": SUBJECT_TOKEN_TYPE,
            "token_url": TOKEN_URL,
            "credential_source": self.CREDENTIAL_SOURCE_TEXT,
        }
        config_file = tmpdir.join("config.json")
        config_file.write(json.dumps(info))
        credentials = identity_pool.Credentials.from_file(str(config_file))

        # Confirm identity_pool.Credentials instantiated with expected attributes.
        assert isinstance(credentials, identity_pool.Credentials)
        mock_init.assert_called_once_with(
            audience=AUDIENCE,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            token_info_url=None,
            service_account_impersonation_url=None,
            service_account_impersonation_options={},
            client_id=None,
            client_secret=None,
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            subject_token_supplier=None,
            quota_project_id=None,
            workforce_pool_user_project=None,
            universe_domain=DEFAULT_UNIVERSE_DOMAIN,
        )

    @mock.patch.object(identity_pool.Credentials, "__init__", return_value=None)
    def test_from_file_workforce_pool(self, mock_init, tmpdir):
        info = {
            "audience": WORKFORCE_AUDIENCE,
            "subject_token_type": WORKFORCE_SUBJECT_TOKEN_TYPE,
            "token_url": TOKEN_URL,
            "credential_source": self.CREDENTIAL_SOURCE_TEXT,
            "workforce_pool_user_project": WORKFORCE_POOL_USER_PROJECT,
        }
        config_file = tmpdir.join("config.json")
        config_file.write(json.dumps(info))
        credentials = identity_pool.Credentials.from_file(str(config_file))

        # Confirm identity_pool.Credentials instantiated with expected attributes.
        assert isinstance(credentials, identity_pool.Credentials)
        mock_init.assert_called_once_with(
            audience=WORKFORCE_AUDIENCE,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            token_info_url=None,
            service_account_impersonation_url=None,
            service_account_impersonation_options={},
            client_id=None,
            client_secret=None,
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            subject_token_supplier=None,
            quota_project_id=None,
            workforce_pool_user_project=WORKFORCE_POOL_USER_PROJECT,
            universe_domain=DEFAULT_UNIVERSE_DOMAIN,
        )

    def test_constructor_nonworkforce_with_workforce_pool_user_project(self):
        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(
                audience=AUDIENCE,
                workforce_pool_user_project=WORKFORCE_POOL_USER_PROJECT,
            )

        assert excinfo.match(
            "workforce_pool_user_project should not be set for non-workforce "
            "pool credentials"
        )

    def test_constructor_invalid_options(self):
        credential_source = {"unsupported": "value"}

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(r"Missing credential_source")

    def test_constructor_invalid_options_url_and_file(self):
        credential_source = {
            "url": self.CREDENTIAL_URL,
            "file": SUBJECT_TOKEN_TEXT_FILE,
        }

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(r"Ambiguous credential_source")

    def test_constructor_invalid_options_url_and_certificate(self):
        credential_source = {
            "url": self.CREDENTIAL_URL,
            "certificate": {"certificate": {"use_default_certificate_config": True}},
        }

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(r"Ambiguous credential_source")

    def test_constructor_invalid_options_file_and_certificate(self):
        credential_source = {
            "file": SUBJECT_TOKEN_TEXT_FILE,
            "certificate": {"certificate": {"use_default_certificate": True}},
        }

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(r"Ambiguous credential_source")

    def test_constructor_invalid_options_url_file_and_certificate(self):
        credential_source = {
            "file": SUBJECT_TOKEN_TEXT_FILE,
            "url": self.CREDENTIAL_URL,
            "certificate": {"certificate": {"use_default_certificate": True}},
        }

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(r"Ambiguous credential_source")

    def test_constructor_invalid_options_environment_id(self):
        credential_source = {"url": self.CREDENTIAL_URL, "environment_id": "aws1"}

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(
            r"Invalid Identity Pool credential_source field 'environment_id'"
        )

    def test_constructor_invalid_credential_source(self):
        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source="non-dict")

        assert excinfo.match(
            r"Invalid credential_source. The credential_source is not a dict."
        )

    def test_constructor_invalid_no_credential_source_or_supplier(self):
        with pytest.raises(ValueError) as excinfo:
            self.make_credentials()

        assert excinfo.match(
            r"A valid credential source or a subject token supplier must be provided."
        )

    def test_constructor_invalid_both_credential_source_and_supplier(self):
        supplier = TestSubjectTokenSupplier()
        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(
                credential_source=self.CREDENTIAL_SOURCE_TEXT,
                subject_token_supplier=supplier,
            )

        assert excinfo.match(
            r"Identity pool credential cannot have both a credential source and a subject token supplier."
        )

    def test_constructor_invalid_credential_source_format_type(self):
        credential_source = {"file": "test.txt", "format": {"type": "xml"}}

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(r"Invalid credential_source format 'xml'")

    def test_constructor_missing_subject_token_field_name(self):
        credential_source = {"file": "test.txt", "format": {"type": "json"}}

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(
            r"Missing subject_token_field_name for JSON credential_source format"
        )

    def test_constructor_default_and_file_location_certificate(self):
        credential_source = {
            "certificate": {
                "use_default_certificate_config": True,
                "certificate_config_location": "test",
            }
        }

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(r"Invalid certificate configuration")

    def test_constructor_no_default_or_file_location_certificate(self):
        credential_source = {"certificate": {"use_default_certificate_config": False}}

        with pytest.raises(ValueError) as excinfo:
            self.make_credentials(credential_source=credential_source)

        assert excinfo.match(r"Invalid certificate configuration")

    def test_info_with_workforce_pool_user_project(self):
        credentials = self.make_credentials(
            audience=WORKFORCE_AUDIENCE,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            credential_source=self.CREDENTIAL_SOURCE_TEXT_URL.copy(),
            workforce_pool_user_project=WORKFORCE_POOL_USER_PROJECT,
        )

        assert credentials.info == {
            "type": "external_account",
            "audience": WORKFORCE_AUDIENCE,
            "subject_token_type": WORKFORCE_SUBJECT_TOKEN_TYPE,
            "token_url": TOKEN_URL,
            "token_info_url": TOKEN_INFO_URL,
            "credential_source": self.CREDENTIAL_SOURCE_TEXT_URL,
            "workforce_pool_user_project": WORKFORCE_POOL_USER_PROJECT,
            "universe_domain": DEFAULT_UNIVERSE_DOMAIN,
        }

    def test_info_with_file_credential_source(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_TEXT_URL.copy()
        )

        assert credentials.info == {
            "type": "external_account",
            "audience": AUDIENCE,
            "subject_token_type": SUBJECT_TOKEN_TYPE,
            "token_url": TOKEN_URL,
            "token_info_url": TOKEN_INFO_URL,
            "credential_source": self.CREDENTIAL_SOURCE_TEXT_URL,
            "universe_domain": DEFAULT_UNIVERSE_DOMAIN,
        }

    def test_info_with_url_credential_source(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_JSON_URL.copy()
        )

        assert credentials.info == {
            "type": "external_account",
            "audience": AUDIENCE,
            "subject_token_type": SUBJECT_TOKEN_TYPE,
            "token_url": TOKEN_URL,
            "token_info_url": TOKEN_INFO_URL,
            "credential_source": self.CREDENTIAL_SOURCE_JSON_URL,
            "universe_domain": DEFAULT_UNIVERSE_DOMAIN,
        }

    def test_info_with_certificate_credential_source(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_CERTIFICATE.copy()
        )

        assert credentials.info == {
            "type": "external_account",
            "audience": AUDIENCE,
            "subject_token_type": SUBJECT_TOKEN_TYPE,
            "token_url": TOKEN_URL,
            "token_info_url": TOKEN_INFO_URL,
            "credential_source": self.CREDENTIAL_SOURCE_CERTIFICATE,
            "universe_domain": DEFAULT_UNIVERSE_DOMAIN,
        }

    def test_info_with_non_default_certificate_credential_source(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_CERTIFICATE_NOT_DEFAULT.copy()
        )

        assert credentials.info == {
            "type": "external_account",
            "audience": AUDIENCE,
            "subject_token_type": SUBJECT_TOKEN_TYPE,
            "token_url": TOKEN_URL,
            "token_info_url": TOKEN_INFO_URL,
            "credential_source": self.CREDENTIAL_SOURCE_CERTIFICATE_NOT_DEFAULT,
            "universe_domain": DEFAULT_UNIVERSE_DOMAIN,
        }

    def test_info_with_default_token_url(self):
        credentials = identity_pool.Credentials(
            audience=AUDIENCE,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            credential_source=self.CREDENTIAL_SOURCE_TEXT_URL.copy(),
        )

        assert credentials.info == {
            "type": "external_account",
            "audience": AUDIENCE,
            "subject_token_type": SUBJECT_TOKEN_TYPE,
            "token_url": TOKEN_URL,
            "credential_source": self.CREDENTIAL_SOURCE_TEXT_URL,
            "universe_domain": DEFAULT_UNIVERSE_DOMAIN,
        }

    def test_info_with_default_token_url_with_universe_domain(self):
        credentials = identity_pool.Credentials(
            audience=AUDIENCE,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            credential_source=self.CREDENTIAL_SOURCE_TEXT_URL.copy(),
            universe_domain="testdomain.org",
        )

        assert credentials.info == {
            "type": "external_account",
            "audience": AUDIENCE,
            "subject_token_type": SUBJECT_TOKEN_TYPE,
            "token_url": "https://sts.testdomain.org/v1/token",
            "credential_source": self.CREDENTIAL_SOURCE_TEXT_URL,
            "universe_domain": "testdomain.org",
        }

    def test_retrieve_subject_token_missing_subject_token(self, tmpdir):
        # Provide empty text file.
        empty_file = tmpdir.join("empty.txt")
        empty_file.write("")
        credential_source = {"file": str(empty_file)}
        credentials = self.make_credentials(credential_source=credential_source)

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(None)

        assert excinfo.match(r"Missing subject_token in the credential_source file")

    def test_retrieve_subject_token_text_file(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_TEXT
        )

        subject_token = credentials.retrieve_subject_token(None)

        assert subject_token == TEXT_FILE_SUBJECT_TOKEN

    def test_retrieve_subject_token_json_file(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_JSON
        )

        subject_token = credentials.retrieve_subject_token(None)

        assert subject_token == JSON_FILE_SUBJECT_TOKEN

    @mock.patch(
        "google.auth.transport._mtls_helper._get_workload_cert_and_key_paths",
        return_value=(CERT_FILE, KEY_FILE),
    )
    def test_retrieve_subject_token_certificate_default(
        self, mock_get_workload_cert_and_key_paths
    ):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_CERTIFICATE
        )

        subject_token = credentials.retrieve_subject_token(None)

        assert subject_token == json.dumps([CERT_FILE_CONTENT])

    @mock.patch(
        "google.auth.transport._mtls_helper._get_workload_cert_and_key_paths",
        return_value=(CERT_FILE, KEY_FILE),
    )
    def test_retrieve_subject_token_certificate_non_default_path(
        self, mock_get_workload_cert_and_key_paths
    ):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_CERTIFICATE_NOT_DEFAULT
        )

        subject_token = credentials.retrieve_subject_token(None)

        assert subject_token == json.dumps([CERT_FILE_CONTENT])

    @mock.patch(
        "google.auth.transport._mtls_helper._get_workload_cert_and_key_paths",
        return_value=(CERT_FILE, KEY_FILE),
    )
    def test_retrieve_subject_token_certificate_trust_chain_with_leaf(
        self, mock_get_workload_cert_and_key_paths
    ):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_CERTIFICATE_TRUST_CHAIN_WITH_LEAF
        )

        subject_token = credentials.retrieve_subject_token(None)
        assert subject_token == json.dumps([CERT_FILE_CONTENT, OTHER_CERT_FILE_CONTENT])

    @mock.patch(
        "google.auth.transport._mtls_helper._get_workload_cert_and_key_paths",
        return_value=(CERT_FILE, KEY_FILE),
    )
    def test_retrieve_subject_token_certificate_trust_chain_without_leaf(
        self, mock_get_workload_cert_and_key_paths
    ):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_CERTIFICATE_TRUST_CHAIN_WITHOUT_LEAF
        )

        subject_token = credentials.retrieve_subject_token(None)
        assert subject_token == json.dumps([CERT_FILE_CONTENT, OTHER_CERT_FILE_CONTENT])

    @mock.patch(
        "google.auth.transport._mtls_helper._get_workload_cert_and_key_paths",
        return_value=(CERT_FILE, KEY_FILE),
    )
    def test_retrieve_subject_token_certificate_trust_chain_invalid_order(
        self, mock_get_workload_cert_and_key_paths
    ):

        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_CERTIFICATE_TRUST_CHAIN_WRONG_ORDER
        )

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(None)

        assert excinfo.match(
            "The leaf certificate must be at the top of the trust chain file"
        )

    @mock.patch(
        "google.auth.transport._mtls_helper._get_workload_cert_and_key_paths",
        return_value=(CERT_FILE, KEY_FILE),
    )
    def test_retrieve_subject_token_certificate_trust_chain_file_does_not_exist(
        self, mock_get_workload_cert_and_key_paths
    ):

        credentials = self.make_credentials(
            credential_source={
                "certificate": {
                    "use_default_certificate_config": "true",
                    "trust_chain_path": "fake.pem",
                }
            }
        )

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(None)

        assert excinfo.match("Trust chain file 'fake.pem' was not found.")

    @mock.patch(
        "google.auth.transport._mtls_helper._get_workload_cert_and_key_paths",
        return_value=(CERT_FILE, KEY_FILE),
    )
    def test_retrieve_subject_token_certificate_invalid_trust_chain_file(
        self, mock_get_workload_cert_and_key_paths
    ):

        credentials = self.make_credentials(
            credential_source={
                "certificate": {
                    "use_default_certificate_config": "true",
                    "trust_chain_path": SUBJECT_TOKEN_TEXT_FILE,
                }
            }
        )

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(None)

        assert excinfo.match("Error loading PEM certificates from the trust chain file")

    def test_retrieve_subject_token_json_file_invalid_field_name(self):
        credential_source = {
            "file": SUBJECT_TOKEN_JSON_FILE,
            "format": {"type": "json", "subject_token_field_name": "not_found"},
        }
        credentials = self.make_credentials(credential_source=credential_source)

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(None)

        assert excinfo.match(
            "Unable to parse subject_token from JSON file '{}' using key '{}'".format(
                SUBJECT_TOKEN_JSON_FILE, "not_found"
            )
        )

    def test_retrieve_subject_token_invalid_json(self, tmpdir):
        # Provide JSON file. This should result in JSON parsing error.
        invalid_json_file = tmpdir.join("invalid.json")
        invalid_json_file.write("{")
        credential_source = {
            "file": str(invalid_json_file),
            "format": {"type": "json", "subject_token_field_name": "access_token"},
        }
        credentials = self.make_credentials(credential_source=credential_source)

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(None)

        assert excinfo.match(
            "Unable to parse subject_token from JSON file '{}' using key '{}'".format(
                str(invalid_json_file), "access_token"
            )
        )

    def test_retrieve_subject_token_file_not_found(self):
        credential_source = {"file": "./not_found.txt"}
        credentials = self.make_credentials(credential_source=credential_source)

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(None)

        assert excinfo.match(r"File './not_found.txt' was not found")

    def test_token_info_url(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_JSON
        )

        assert credentials.token_info_url == TOKEN_INFO_URL

    def test_token_info_url_custom(self):
        for url in VALID_TOKEN_URLS:
            credentials = self.make_credentials(
                credential_source=self.CREDENTIAL_SOURCE_JSON.copy(),
                token_info_url=(url + "/introspect"),
            )

            assert credentials.token_info_url == url + "/introspect"

    def test_token_info_url_negative(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_JSON.copy(), token_info_url=None
        )

        assert not credentials.token_info_url

    def test_token_url_custom(self):
        for url in VALID_TOKEN_URLS:
            credentials = self.make_credentials(
                credential_source=self.CREDENTIAL_SOURCE_JSON.copy(),
                token_url=(url + "/token"),
            )

            assert credentials._token_url == (url + "/token")

    def test_service_account_impersonation_url_custom(self):
        for url in VALID_SERVICE_ACCOUNT_IMPERSONATION_URLS:
            credentials = self.make_credentials(
                credential_source=self.CREDENTIAL_SOURCE_JSON.copy(),
                service_account_impersonation_url=(
                    url + SERVICE_ACCOUNT_IMPERSONATION_URL_ROUTE
                ),
            )

            assert credentials._service_account_impersonation_url == (
                url + SERVICE_ACCOUNT_IMPERSONATION_URL_ROUTE
            )

    def test_refresh_text_file_success_without_impersonation_ignore_default_scopes(
        self,
    ):
        credentials = self.make_credentials(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            scopes=SCOPES,
            # Default scopes should be ignored.
            default_scopes=["ignored"],
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=None,
            basic_auth_encoding=BASIC_AUTH_ENCODING,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=["ignored"],
        )

    def test_refresh_workforce_success_with_client_auth_without_impersonation(self):
        credentials = self.make_credentials(
            audience=WORKFORCE_AUDIENCE,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            scopes=SCOPES,
            # This will be ignored in favor of client auth.
            workforce_pool_user_project=WORKFORCE_POOL_USER_PROJECT,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=WORKFORCE_AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=None,
            basic_auth_encoding=BASIC_AUTH_ENCODING,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            workforce_pool_user_project=None,
        )

    def test_refresh_workforce_success_with_client_auth_and_no_workforce_project(self):
        credentials = self.make_credentials(
            audience=WORKFORCE_AUDIENCE,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            scopes=SCOPES,
            # This is not needed when client Auth is used.
            workforce_pool_user_project=None,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=WORKFORCE_AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=None,
            basic_auth_encoding=BASIC_AUTH_ENCODING,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            workforce_pool_user_project=None,
        )

    def test_refresh_workforce_success_without_client_auth_without_impersonation(self):
        credentials = self.make_credentials(
            audience=WORKFORCE_AUDIENCE,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            client_id=None,
            client_secret=None,
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            scopes=SCOPES,
            # This will not be ignored as client auth is not used.
            workforce_pool_user_project=WORKFORCE_POOL_USER_PROJECT,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=WORKFORCE_AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=None,
            basic_auth_encoding=None,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            workforce_pool_user_project=WORKFORCE_POOL_USER_PROJECT,
        )

    def test_refresh_workforce_success_without_client_auth_with_impersonation(self):
        credentials = self.make_credentials(
            audience=WORKFORCE_AUDIENCE,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            client_id=None,
            client_secret=None,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            scopes=SCOPES,
            # This will not be ignored as client auth is not used.
            workforce_pool_user_project=WORKFORCE_POOL_USER_PROJECT,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=WORKFORCE_AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=WORKFORCE_SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            basic_auth_encoding=None,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            workforce_pool_user_project=WORKFORCE_POOL_USER_PROJECT,
        )

    def test_refresh_text_file_success_without_impersonation_use_default_scopes(self):
        credentials = self.make_credentials(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            scopes=None,
            # Default scopes should be used since user specified scopes are none.
            default_scopes=SCOPES,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=None,
            basic_auth_encoding=BASIC_AUTH_ENCODING,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=None,
            default_scopes=SCOPES,
        )

    def test_refresh_text_file_success_with_impersonation_ignore_default_scopes(self):
        # Initialize credentials with service account impersonation and basic auth.
        credentials = self.make_credentials(
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            scopes=SCOPES,
            # Default scopes should be ignored.
            default_scopes=["ignored"],
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            basic_auth_encoding=None,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=["ignored"],
        )

    def test_refresh_text_file_success_with_impersonation_use_default_scopes(self):
        # Initialize credentials with service account impersonation, basic auth
        # and default scopes (no user scopes).
        credentials = self.make_credentials(
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            scopes=None,
            # Default scopes should be used since user specified scopes are none.
            default_scopes=SCOPES,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            basic_auth_encoding=None,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=None,
            default_scopes=SCOPES,
        )

    def test_refresh_json_file_success_without_impersonation(self):
        credentials = self.make_credentials(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            # Test with JSON format type.
            credential_source=self.CREDENTIAL_SOURCE_JSON,
            scopes=SCOPES,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=JSON_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=None,
            basic_auth_encoding=BASIC_AUTH_ENCODING,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=None,
        )

    def test_refresh_json_file_success_with_impersonation(self):
        # Initialize credentials with service account impersonation and basic auth.
        credentials = self.make_credentials(
            # Test with JSON format type.
            credential_source=self.CREDENTIAL_SOURCE_JSON,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            scopes=SCOPES,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=JSON_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            basic_auth_encoding=None,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=None,
        )

    def test_refresh_with_retrieve_subject_token_error(self):
        credential_source = {
            "file": SUBJECT_TOKEN_JSON_FILE,
            "format": {"type": "json", "subject_token_field_name": "not_found"},
        }
        credentials = self.make_credentials(credential_source=credential_source)

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.refresh(None)

        assert excinfo.match(
            "Unable to parse subject_token from JSON file '{}' using key '{}'".format(
                SUBJECT_TOKEN_JSON_FILE, "not_found"
            )
        )

    def test_retrieve_subject_token_from_url(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_TEXT_URL
        )
        request = self.make_mock_request(token_data=TEXT_FILE_SUBJECT_TOKEN)
        subject_token = credentials.retrieve_subject_token(request)

        assert subject_token == TEXT_FILE_SUBJECT_TOKEN
        self.assert_credential_request_kwargs(request.call_args_list[0][1], None)

    def test_retrieve_subject_token_from_url_with_headers(self):
        credentials = self.make_credentials(
            credential_source={"url": self.CREDENTIAL_URL, "headers": {"foo": "bar"}}
        )
        request = self.make_mock_request(token_data=TEXT_FILE_SUBJECT_TOKEN)
        subject_token = credentials.retrieve_subject_token(request)

        assert subject_token == TEXT_FILE_SUBJECT_TOKEN
        self.assert_credential_request_kwargs(
            request.call_args_list[0][1], {"foo": "bar"}
        )

    def test_retrieve_subject_token_from_url_json(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_JSON_URL
        )
        request = self.make_mock_request(token_data=JSON_FILE_CONTENT)
        subject_token = credentials.retrieve_subject_token(request)

        assert subject_token == JSON_FILE_SUBJECT_TOKEN
        self.assert_credential_request_kwargs(request.call_args_list[0][1], None)

    def test_retrieve_subject_token_from_url_json_with_headers(self):
        credentials = self.make_credentials(
            credential_source={
                "url": self.CREDENTIAL_URL,
                "format": {"type": "json", "subject_token_field_name": "access_token"},
                "headers": {"foo": "bar"},
            }
        )
        request = self.make_mock_request(token_data=JSON_FILE_CONTENT)
        subject_token = credentials.retrieve_subject_token(request)

        assert subject_token == JSON_FILE_SUBJECT_TOKEN
        self.assert_credential_request_kwargs(
            request.call_args_list[0][1], {"foo": "bar"}
        )

    def test_retrieve_subject_token_from_url_not_found(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_TEXT_URL
        )
        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(
                self.make_mock_request(token_status=404, token_data=JSON_FILE_CONTENT)
            )

        assert excinfo.match("Unable to retrieve Identity Pool subject token")

    def test_retrieve_subject_token_from_url_json_invalid_field(self):
        credential_source = {
            "url": self.CREDENTIAL_URL,
            "format": {"type": "json", "subject_token_field_name": "not_found"},
        }
        credentials = self.make_credentials(credential_source=credential_source)

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(
                self.make_mock_request(token_data=JSON_FILE_CONTENT)
            )

        assert excinfo.match(
            "Unable to parse subject_token from JSON file '{}' using key '{}'".format(
                self.CREDENTIAL_URL, "not_found"
            )
        )

    def test_retrieve_subject_token_from_url_json_invalid_format(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_JSON_URL
        )

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.retrieve_subject_token(self.make_mock_request(token_data="{"))

        assert excinfo.match(
            "Unable to parse subject_token from JSON file '{}' using key '{}'".format(
                self.CREDENTIAL_URL, "access_token"
            )
        )

    def test_refresh_text_file_success_without_impersonation_url(self):
        credentials = self.make_credentials(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT_URL,
            scopes=SCOPES,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=None,
            basic_auth_encoding=BASIC_AUTH_ENCODING,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=None,
            credential_data=TEXT_FILE_SUBJECT_TOKEN,
        )

    def test_refresh_text_file_success_with_impersonation_url(self):
        # Initialize credentials with service account impersonation and basic auth.
        credentials = self.make_credentials(
            # Test with text format type.
            credential_source=self.CREDENTIAL_SOURCE_TEXT_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            scopes=SCOPES,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            basic_auth_encoding=None,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=None,
            credential_data=TEXT_FILE_SUBJECT_TOKEN,
        )

    def test_refresh_json_file_success_without_impersonation_url(self):
        credentials = self.make_credentials(
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            # Test with JSON format type.
            credential_source=self.CREDENTIAL_SOURCE_JSON_URL,
            scopes=SCOPES,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=JSON_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=None,
            basic_auth_encoding=BASIC_AUTH_ENCODING,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=None,
            credential_data=JSON_FILE_CONTENT,
        )

    def test_refresh_json_file_success_with_impersonation_url(self):
        # Initialize credentials with service account impersonation and basic auth.
        credentials = self.make_credentials(
            # Test with JSON format type.
            credential_source=self.CREDENTIAL_SOURCE_JSON_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            scopes=SCOPES,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=JSON_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            basic_auth_encoding=None,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=None,
            credential_data=JSON_FILE_CONTENT,
        )

    def test_refresh_with_retrieve_subject_token_error_url(self):
        credential_source = {
            "url": self.CREDENTIAL_URL,
            "format": {"type": "json", "subject_token_field_name": "not_found"},
        }
        credentials = self.make_credentials(credential_source=credential_source)

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.refresh(self.make_mock_request(token_data=JSON_FILE_CONTENT))

        assert excinfo.match(
            "Unable to parse subject_token from JSON file '{}' using key '{}'".format(
                self.CREDENTIAL_URL, "not_found"
            )
        )

    def test_retrieve_subject_token_supplier(self):
        supplier = TestSubjectTokenSupplier(subject_token=JSON_FILE_SUBJECT_TOKEN)

        credentials = self.make_credentials(subject_token_supplier=supplier)

        subject_token = credentials.retrieve_subject_token(None)

        assert subject_token == JSON_FILE_SUBJECT_TOKEN

    def test_retrieve_subject_token_supplier_correct_context(self):
        supplier = TestSubjectTokenSupplier(
            subject_token=JSON_FILE_SUBJECT_TOKEN,
            expected_context=external_account.SupplierContext(
                SUBJECT_TOKEN_TYPE, AUDIENCE
            ),
        )

        credentials = self.make_credentials(subject_token_supplier=supplier)

        credentials.retrieve_subject_token(None)

    def test_retrieve_subject_token_supplier_error(self):
        expected_exception = exceptions.RefreshError("test error")
        supplier = TestSubjectTokenSupplier(subject_token_exception=expected_exception)

        credentials = self.make_credentials(subject_token_supplier=supplier)

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials.refresh(self.make_mock_request(token_data=JSON_FILE_CONTENT))

        assert excinfo.match("test error")

    def test_refresh_success_supplier_with_impersonation_url(self):
        # Initialize credentials with service account impersonation and a supplier.
        supplier = TestSubjectTokenSupplier(subject_token=JSON_FILE_SUBJECT_TOKEN)
        credentials = self.make_credentials(
            subject_token_supplier=supplier,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            scopes=SCOPES,
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            service_account_impersonation_url=SERVICE_ACCOUNT_IMPERSONATION_URL,
            basic_auth_encoding=None,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=None,
        )

    def test_refresh_success_supplier_without_impersonation_url(self):
        # Initialize supplier credentials without service account impersonation.
        supplier = TestSubjectTokenSupplier(subject_token=JSON_FILE_SUBJECT_TOKEN)
        credentials = self.make_credentials(
            subject_token_supplier=supplier, scopes=SCOPES
        )

        self.assert_underlying_credentials_refresh(
            credentials=credentials,
            audience=AUDIENCE,
            subject_token=TEXT_FILE_SUBJECT_TOKEN,
            subject_token_type=SUBJECT_TOKEN_TYPE,
            token_url=TOKEN_URL,
            basic_auth_encoding=None,
            quota_project_id=None,
            used_scopes=SCOPES,
            scopes=SCOPES,
            default_scopes=None,
        )

    @mock.patch(
        "google.auth.transport._mtls_helper._get_workload_cert_and_key_paths",
        return_value=("cert", "key"),
    )
    def test_get_mtls_certs(self, mock_get_workload_cert_and_key_paths):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_CERTIFICATE.copy()
        )

        cert, key = credentials._get_mtls_cert_and_key_paths()
        assert cert == "cert"
        assert key == "key"

    def test_get_mtls_certs_invalid(self):
        credentials = self.make_credentials(
            credential_source=self.CREDENTIAL_SOURCE_TEXT.copy()
        )

        with pytest.raises(exceptions.RefreshError) as excinfo:
            credentials._get_mtls_cert_and_key_paths()

        assert excinfo.match(
            'The credential is not configured to use mtls requests. The credential should include a "certificate" section in the credential source.'
        )
