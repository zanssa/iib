# SPDX-License-Identifier: GPL-3.0-or-later
import os
import logging
import types

from iib.exceptions import ConfigError


class Config(object):
    """The base IIB Celery configuration."""

    # When publishing a message, don't continuously retry or else the HTTP connection times out
    broker_transport_options = {'max_retries': 10}
    # Avoid infinite Celery retries when the broker is offline.
    broker_connection_max_retries: int = 10
    iib_aws_s3_bucket_name = None
    iib_api_timeout = 30
    iib_docker_config_template = os.path.join(
        os.path.expanduser('~'), '.docker', 'config.json.template'
    )
    iib_greenwave_url = None
    iib_grpc_init_wait_time = 30
    iib_grpc_max_port_tries = 100
    iib_grpc_max_tries = 5
    iib_grpc_start_port = 50051
    iib_image_push_template = '{registry}/iib-build:{request_id}'
    iib_index_image_output_registry = None
    iib_log_level = 'INFO'
    iib_organization_customizations = {}
    iib_request_logs_dir = None
    iib_request_logs_format = (
        '%(asctime)s %(name)s %(processName)s {request_id} '
        '%(levelname)s %(module)s.%(funcName)s %(message)s'
    )
    iib_request_logs_level = 'DEBUG'
    iib_required_labels = {}
    iib_request_related_bundles_dir = None
    # Configuration for dogpile.cache
    # Disabled by default (by using 'dogpile.cache.null').
    # To enable caching set 'dogpile.cache.memcached' as backend.
    iib_dogpile_backend = 'dogpile.cache.null'
    iib_dogpile_expiration_time = 600
    iib_dogpile_arguments = {'url': ['127.0.0.1']}
    iib_skopeo_timeout = '300s'
    iib_total_attempts: int = 5
    iib_retry_delay: int = 4
    iib_retry_jitter: int = 2
    include = [
        'iib.workers.tasks.build',
        'iib.workers.tasks.build_merge_index_image',
        'iib.workers.tasks.build_regenerate_bundle',
        'iib.workers.tasks.build_create_empty_index',
        'iib.workers.tasks.general',
    ]
    # Path to hidden location of SQLite database
    hidden_index_db_path = '/var/lib/iib/_hidden/do.not.edit.db'
    # The task messages will be acknowledged after the task has been executed,
    # instead of just before
    task_acks_late = True
    # Don't use the default 'celery' queue and routing key
    task_default_queue = 'iib'
    task_default_routing_key = 'iib'
    # Requeue the message if the worker abruptly exits or is signaled
    task_reject_on_worker_lost = True
    # Path to index.db in our temp directories used in IIB code
    temp_index_db_path = 'database/index.db'
    # For now, only allow a single process so that all tasks are processed serially
    worker_concurrency = 1
    # Don't allow the worker to fetch more messages than it can handle at a time. This is so that
    # other tasks aren't starved. This will only be useful once more workers are enabled.
    worker_prefetch_multiplier = 1
    # Enable send events to the broker. This is needed for celery promethues exporter
    worker_send_task_events = True
    task_send_sent_event = True


class ProductionConfig(Config):
    """The production IIB Celery configuration."""


class DevelopmentConfig(Config):
    """The development IIB Celery configuration."""

    broker_url = 'amqp://iib:iib@rabbitmq:5673//'
    iib_api_url = 'http://iib-api:8080/api/v1/'
    iib_log_level = 'DEBUG'
    iib_organization_customizations = {
        'company-marketplace': [
            {'type': 'resolve_image_pullspecs'},
            {'type': 'related_bundles'},
            {
                'type': 'csv_annotations',
                'annotations': {
                    'marketplace.company.io/remote-workflow': (
                        'https://marketplace.company.com/en-us/operators/{package_name}/pricing'
                    ),
                    'marketplace.company.io/support-workflow': (
                        'https://marketplace.company.com/en-us/operators/{package_name}/support'
                    ),
                },
            },
            {'type': 'package_name_suffix', 'suffix': '-cmp'},
            {
                'type': 'registry_replacements',
                'replacements': {
                    'registry.access.company.com': 'registry.marketplace.company.com/cm',
                },
            },
            {'type': 'image_name_from_labels', 'template': '{name}-{version}-final'},
        ],
        'company-managed': [
            {'type': 'package_name_suffix', 'suffix': '-cmp'},
            {
                'type': 'csv_annotations',
                'annotations': {
                    'marketplace.company.io/remote-workflow': (
                        'https://marketplace.company.com/en-us/operators/{package_name}/pricing'
                    ),
                    'marketplace.company.io/support-workflow': (
                        'https://marketplace.company.com/en-us/operators/{package_name}/support'
                    ),
                },
            },
            {
                'type': 'registry_replacements',
                'replacements': {
                    'registry.access.company.com': 'registry.koji.company.com',
                    'quay.io': 'registry.koji.company.com',
                },
            },
            {'type': 'related_bundles'},
            {'type': 'image_name_from_labels', 'template': '{name}-{version}'},
            {'type': 'enclose_repo', 'enclosure_glue': '----', 'namespace': "company-pending"},
            {
                'type': 'registry_replacements',
                'replacements': {'registry.koji.company.com': 'quaaay.com'},
            },
        ],
    }
    iib_registry = 'registry:8443'
    iib_request_logs_dir = '/var/log/iib/requests'
    iib_request_related_bundles_dir = '/var/lib/requests/related_bundles'
    iib_dogpile_backend = 'dogpile.cache.memcached'


class TestingConfig(DevelopmentConfig):
    """The testing IIB Celery configuration."""

    iib_docker_config_template = '/home/iib-worker/.docker/config.json.template'
    iib_greenwave_url = 'some_url'
    iib_omps_url = 'some_url'
    iib_request_logs_dir = None
    iib_request_related_bundles_dir = None
    # disable dogpile cache for tests
    iib_dogpile_backend = 'dogpile.cache.null'


def configure_celery(celery_app):
    """
    Configure the Celery application instance.

    :param celery.Celery celery: the Celery application instance to configure
    """
    config = ProductionConfig
    prod_config_file_path = os.getenv('IIB_CELERY_CONFIG', '/etc/iib/celery.py')
    if os.getenv('IIB_DEV', '').lower() == 'true':
        config = DevelopmentConfig
    elif os.getenv('IIB_TESTING', 'false').lower() == 'true':
        config = TestingConfig
    elif os.path.isfile(prod_config_file_path):
        # Celery doesn't support importing config files that aren't part of a Python path. This is
        # a hack taken from flask.config.from_pyfile.
        _user_config = {}
        # FIXME: Bandit complaining on use of exec - CLOUDDST-11306
        with open(prod_config_file_path, mode='rb') as config_file:
            exec(compile(config_file.read(), prod_config_file_path, 'exec'), _user_config)  # nosec

        # Celery doesn't support configuring from multiple objects, so this is a way for
        # the configuration in prod_config_file_path to override the defaults in ProductionConfig
        config = ProductionConfig()
        for key, value in _user_config.items():
            # The _user_config dictionary will contain the __builtins__ key, which we need to skip.
            # Additionally, if any modules were imported to define Celery queues, they will
            # be ignored.
            if not key.startswith('__') and not isinstance(value, types.ModuleType):
                setattr(config, key, value)

    celery_app.config_from_object(config, force=True)
    logging.getLogger('iib.workers').setLevel(celery_app.conf.iib_log_level)


def validate_celery_config(conf, **kwargs):
    """
    Perform basic validatation on the Celery configuration when the worker is initialized.

    :param celery.app.utils.Settings conf: the Celery application configuration to validate
    :raises iib.exceptions.ConfigError: if the configuration is invalid
    """
    if not conf.get('iib_registry'):
        raise ConfigError('iib_registry must be set to the destination container registry')

    if not conf.get('iib_api_url'):
        raise ConfigError('iib_api_url must be set')

    if not isinstance(conf['iib_required_labels'], dict):
        raise ConfigError('iib_required_labels must be a dictionary')

    _validate_iib_org_customizations(conf['iib_organization_customizations'])

    if conf.get('iib_aws_s3_bucket_name'):
        if not isinstance(conf['iib_aws_s3_bucket_name'], str):
            raise ConfigError(
                '"iib_aws_s3_bucket_name" must be set to a valid string. '
                'This is used for read/write access to the s3 bucket by IIB'
            )
        if not conf.get('iib_request_logs_dir') or not conf.get('iib_request_related_bundles_dir'):
            raise ConfigError(
                '"iib_request_logs_dir" and "iib_request_related_bundles_dir" '
                'must be set when iib_aws_s3_bucket_name is set.'
            )
        if (
            not os.getenv('AWS_ACCESS_KEY_ID')
            or not os.getenv('AWS_SECRET_ACCESS_KEY')
            or not os.getenv('AWS_DEFAULT_REGION')
        ):
            raise ConfigError(
                '"AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY" and "AWS_DEFAULT_REGION" '
                'environment variables must be set to valid strings when'
                '"iib_aws_s3_bucket_name" is set. '
                'These are used for read/write access to the s3 bucket by IIB'
            )

    for directory in ('iib_request_logs_dir', 'iib_request_related_bundles_dir'):
        iib_request_temp_data_dir = conf.get(directory)
        if iib_request_temp_data_dir:
            if not os.path.isdir(iib_request_temp_data_dir):
                raise ConfigError(f'{directory} must exist and be a directory')
            if not os.access(iib_request_temp_data_dir, os.W_OK):
                raise ConfigError(f'{directory}, is not writable!')


def _validate_iib_org_customizations(iib_org_customizations):
    """
    Validate ``iib_organization_customizations`` celery config variable.

    :param dict iib_org_customizations: the value of iib_organization_customizations config
        variable
    :raises iib.exceptions.ConfigError: if the configuration is invalid
    """
    if not isinstance(iib_org_customizations, dict):
        raise ConfigError('iib_organization_customizations must be a dictionary')

    valid_customizations = {
        'csv_annotations': {'annotations'},
        'package_name_suffix': {'suffix'},
        'registry_replacements': {'replacements'},
        'image_name_from_labels': {'template'},
        'enclose_repo': {'enclosure_glue', 'namespace'},
    }

    for org, org_config in iib_org_customizations.items():
        if not isinstance(org, str):
            raise ConfigError('The org keys in iib_organization_customizations must be strings')

        if not isinstance(org_config, list):
            raise ConfigError('The org values in iib_organization_customizations must be a list')

        for customization in org_config:
            if not isinstance(customization, dict):
                raise ConfigError(
                    'Every customization for an org in '
                    'iib_organization_customizations must be dictionary'
                )

            customization_type = customization.get('type')
            if customization_type not in valid_customizations.keys():
                raise ConfigError(
                    f'Invalid customization in iib_organization_customizations {customization}'
                )

            invalid_customization_keys = (
                customization.keys() - valid_customizations[customization_type] - {'type'}
            )
            if invalid_customization_keys:
                raise ConfigError(
                    f'The keys {invalid_customization_keys} in iib_organization_customizations'
                    f'.{org}[{org_config.index(customization)}] are invalid.'
                )

            if customization_type in ('csv_annotations', 'registry_replacements'):
                for valid_key in valid_customizations[customization_type]:
                    if not customization[valid_key]:
                        continue

                    for k, v in customization[valid_key].items():
                        if not isinstance(k, str):
                            raise ConfigError(
                                f'The keys in iib_organization_customizations.{org}'
                                f'[{org_config.index(customization)}].{valid_key} must be strings'
                            )

                        if not isinstance(v, str):
                            raise ConfigError(
                                f'The values in iib_organization_customizations.{org}'
                                f'[{org_config.index(customization)}].{valid_key} must be strings'
                            )

            if customization_type in (
                'package_name_suffix',
                'image_name_from_labels',
                'enclose_repo',
            ):
                for valid_key in valid_customizations[customization_type]:
                    if not isinstance(customization[valid_key], str):
                        raise ConfigError(
                            f'The value of iib_organization_customizations.{org}'
                            f'[{org_config.index(customization)}].{valid_key} must be a string'
                        )


def get_worker_config():
    """Return the Celery configuration."""
    # Import this here to avoid a circular import
    import iib.workers.tasks.celery

    return iib.workers.tasks.celery.app.conf
