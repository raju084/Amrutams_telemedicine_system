"""
Read-Replica Database Router for Amrutam Telemedicine.
Routes read queries from analytics, doctor search, and list views to the
read replica when configured, while keeping all writes on the primary.
"""


class ReadReplicaRouter:
    """
    Database router that directs read traffic to the 'replica' database
    for horizontal read scaling, and all writes to the 'default' primary.
    """

    # Models that are always read from primary (strong consistency required)
    PRIMARY_ONLY_MODELS = {
        'IdempotencyRecord',
        'AvailabilitySlot',
        'Consultation',
        'Payment',
        'AuditLog',
    }

    # Apps whose reads can safely go to the replica (eventual consistency OK)
    REPLICA_SAFE_APPS = {
        'analytics',
        'doctors',
    }

    def db_for_read(self, model, **hints):
        """
        Route reads to replica for safe models/apps; otherwise use primary.
        """
        from django.conf import settings
        if 'replica' not in settings.DATABASES:
            return 'default'

        # Never read from replica for consistency-critical models
        if model.__name__ in self.PRIMARY_ONLY_MODELS:
            return 'default'

        # Route analytics and doctor search queries to replica
        if model._meta.app_label in self.REPLICA_SAFE_APPS:
            return 'replica'

        return 'default'

    def db_for_write(self, model, **hints):
        """All writes always go to the primary database."""
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        """Allow relations between objects in the same or primary/replica pair."""
        db_set = {'default', 'replica'}
        if obj1._state.db in db_set and obj2._state.db in db_set:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Migrations only run on the primary database."""
        return db == 'default'
