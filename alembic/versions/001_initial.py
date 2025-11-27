"""Migration initiale - Création des tables Kobiri

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Créer les types ENUM (avec vérification d'existence)
    op.execute("DO $$ BEGIN CREATE TYPE userrole AS ENUM ('membre', 'president', 'tresorier', 'admin'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE tontinetype AS ENUM ('rotative', 'cumulative', 'mixte'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE tontinefrequency AS ENUM ('quotidien', 'hebdomadaire', 'bimensuel', 'mensuel', 'trimestriel'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE sessionstatus AS ENUM ('programmee', 'en_cours', 'en_attente', 'terminee', 'annulee'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE paymentstatus AS ENUM ('en_attente', 'en_cours', 'valide', 'echoue', 'annule', 'rembourse'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE paymentmethod AS ENUM ('especes', 'orange_money', 'mtn_momo', 'wave', 'free_money', 'moov_money', 'bank_transfer'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE passagestatus AS ENUM ('programme', 'en_cours', 'complete', 'reporte', 'annule'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE notificationtype AS ENUM ('rappel_cotisation', 'confirmation_paiement', 'alerte_retard', 'tour_passage', 'nouveau_membre', 'membre_depart', 'session_ouverte', 'session_terminee', 'paiement_recu', 'penalite', 'information', 'systeme'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE notificationchannel AS ENUM ('sms', 'email', 'push', 'in_app'); EXCEPTION WHEN duplicate_object THEN null; END $$;")
    op.execute("DO $$ BEGIN CREATE TYPE notificationstatus AS ENUM ('en_attente', 'envoyee', 'delivree', 'lue', 'echouee', 'annulee'); EXCEPTION WHEN duplicate_object THEN null; END $$;")

    # Table users
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('first_name', sa.String(length=100), nullable=False),
        sa.Column('last_name', sa.String(length=100), nullable=False),
        sa.Column('profile_picture', sa.String(length=500), nullable=True),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('city', sa.String(length=100), nullable=True),
        sa.Column('country', sa.String(length=100), server_default='Sénégal', nullable=True),
        sa.Column('role', postgresql.ENUM('membre', 'president', 'tresorier', 'admin', name='userrole', create_type=False), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('reset_token', sa.String(length=255), nullable=True),
        sa.Column('reset_token_expires', sa.DateTime(), nullable=True),
        sa.Column('verification_code', sa.String(length=6), nullable=True),
        sa.Column('verification_code_expires', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('phone'),
    )
    op.create_index('idx_user_email_active', 'users', ['email', 'is_active'])
    op.create_index('idx_user_phone_active', 'users', ['phone', 'is_active'])
    op.create_index('idx_user_role', 'users', ['role'])

    # Table tontines
    op.create_table(
        'tontines',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('type', postgresql.ENUM('rotative', 'cumulative', 'mixte', name='tontinetype', create_type=False), nullable=False),
        sa.Column('frequency', postgresql.ENUM('quotidien', 'hebdomadaire', 'bimensuel', 'mensuel', 'trimestriel', name='tontinefrequency', create_type=False), nullable=False),
        sa.Column('contribution_amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), server_default='FCFA', nullable=False),
        sa.Column('max_members', sa.Integer(), server_default='12', nullable=False),
        sa.Column('min_members', sa.Integer(), server_default='3', nullable=False),
        sa.Column('start_date', sa.DateTime(), nullable=False),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('rules', sa.Text(), nullable=True),
        sa.Column('penalty_amount', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
        sa.Column('grace_period_days', sa.Integer(), server_default='3', nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_public', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('idx_tontine_active', 'tontines', ['is_active'])
    op.create_index('idx_tontine_created_by', 'tontines', ['created_by_id'])
    op.create_index('idx_tontine_public_active', 'tontines', ['is_public', 'is_active'])

    # Table tontine_members
    op.create_table(
        'tontine_members',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('tontine_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.String(length=50), server_default='membre', nullable=False),
        sa.Column('order_position', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('joined_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('left_at', sa.DateTime(), nullable=True),
        sa.Column('total_contributions', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('total_received', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('missed_payments', sa.Integer(), server_default='0', nullable=False),
        sa.ForeignKeyConstraint(['tontine_id'], ['tontines.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'tontine_id', name='unique_membership'),
    )
    op.create_index('idx_member_tontine', 'tontine_members', ['tontine_id', 'is_active'])
    op.create_index('idx_member_user', 'tontine_members', ['user_id', 'is_active'])
    op.create_index('idx_member_order', 'tontine_members', ['tontine_id', 'order_position'])

    # Table cotisation_sessions
    op.create_table(
        'cotisation_sessions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tontine_id', sa.Integer(), nullable=False),
        sa.Column('session_number', sa.Integer(), nullable=False),
        sa.Column('scheduled_date', sa.DateTime(), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=False),
        sa.Column('opened_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('status', postgresql.ENUM('programmee', 'en_cours', 'en_attente', 'terminee', 'annulee', name='sessionstatus', create_type=False), nullable=False),
        sa.Column('expected_amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('collected_amount', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('beneficiary_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['beneficiary_id'], ['users.id']),
        sa.ForeignKeyConstraint(['tontine_id'], ['tontines.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_session_tontine', 'cotisation_sessions', ['tontine_id'])
    op.create_index('idx_session_status', 'cotisation_sessions', ['status'])
    op.create_index('idx_session_scheduled', 'cotisation_sessions', ['scheduled_date'])
    op.create_index('idx_session_tontine_number', 'cotisation_sessions', ['tontine_id', 'session_number'])

    # Table payments
    op.create_table(
        'payments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('tontine_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('currency', sa.String(length=10), server_default='FCFA', nullable=False),
        sa.Column('method', postgresql.ENUM('especes', 'orange_money', 'mtn_momo', 'wave', 'free_money', 'moov_money', 'bank_transfer', name='paymentmethod', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('en_attente', 'en_cours', 'valide', 'echoue', 'annule', 'rembourse', name='paymentstatus', create_type=False), nullable=False),
        sa.Column('operator_reference', sa.String(length=100), nullable=True),
        sa.Column('operator_transaction_id', sa.String(length=100), nullable=True),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('operator_callback_data', sa.JSON(), nullable=True),
        sa.Column('proof_url', sa.String(length=500), nullable=True),
        sa.Column('proof_description', sa.Text(), nullable=True),
        sa.Column('validated_by_id', sa.Integer(), nullable=True),
        sa.Column('validated_at', sa.DateTime(), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('penalty_amount', sa.Numeric(precision=10, scale=2), server_default='0', nullable=False),
        sa.Column('is_late', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('initiated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['session_id'], ['cotisation_sessions.id']),
        sa.ForeignKeyConstraint(['tontine_id'], ['tontines.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.ForeignKeyConstraint(['validated_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('operator_reference'),
    )
    op.create_index('idx_payment_user', 'payments', ['user_id'])
    op.create_index('idx_payment_session', 'payments', ['session_id'])
    op.create_index('idx_payment_tontine', 'payments', ['tontine_id'])
    op.create_index('idx_payment_status', 'payments', ['status'])
    op.create_index('idx_payment_method', 'payments', ['method'])
    op.create_index('idx_payment_user_session', 'payments', ['user_id', 'session_id'])
    op.create_index('idx_payment_operator_ref', 'payments', ['operator_reference'])

    # Table passages
    op.create_table(
        'passages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('tontine_id', sa.Integer(), nullable=False),
        sa.Column('member_id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('order_number', sa.Integer(), nullable=False),
        sa.Column('scheduled_date', sa.DateTime(), nullable=False),
        sa.Column('actual_date', sa.DateTime(), nullable=True),
        sa.Column('status', postgresql.ENUM('programme', 'en_cours', 'complete', 'reporte', 'annule', name='passagestatus', create_type=False), nullable=False),
        sa.Column('expected_amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('amount_received', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False),
        sa.Column('payout_method', sa.String(length=50), nullable=True),
        sa.Column('payout_reference', sa.String(length=100), nullable=True),
        sa.Column('payout_phone', sa.String(length=20), nullable=True),
        sa.Column('confirmed_by_member', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('confirmed_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('postpone_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['member_id'], ['tontine_members.id']),
        sa.ForeignKeyConstraint(['session_id'], ['cotisation_sessions.id']),
        sa.ForeignKeyConstraint(['tontine_id'], ['tontines.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tontine_id', 'order_number', name='unique_order_in_tontine'),
        sa.UniqueConstraint('tontine_id', 'member_id', name='unique_member_passage'),
    )
    op.create_index('idx_passage_tontine', 'passages', ['tontine_id'])
    op.create_index('idx_passage_member', 'passages', ['member_id'])
    op.create_index('idx_passage_status', 'passages', ['status'])
    op.create_index('idx_passage_scheduled', 'passages', ['scheduled_date'])
    op.create_index('idx_passage_order', 'passages', ['tontine_id', 'order_number'])

    # Table notifications
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', postgresql.ENUM('rappel_cotisation', 'confirmation_paiement', 'alerte_retard', 'tour_passage', 'nouveau_membre', 'membre_depart', 'session_ouverte', 'session_terminee', 'paiement_recu', 'penalite', 'information', 'systeme', name='notificationtype', create_type=False), nullable=False),
        sa.Column('channel', postgresql.ENUM('sms', 'email', 'push', 'in_app', name='notificationchannel', create_type=False), nullable=False),
        sa.Column('status', postgresql.ENUM('en_attente', 'envoyee', 'delivree', 'lue', 'echouee', 'annulee', name='notificationstatus', create_type=False), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('data', sa.JSON(), nullable=True),
        sa.Column('tontine_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.Integer(), nullable=True),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('scheduled_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('delivered_at', sa.DateTime(), nullable=True),
        sa.Column('read_at', sa.DateTime(), nullable=True),
        sa.Column('provider_message_id', sa.String(length=100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('retry_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['payment_id'], ['payments.id']),
        sa.ForeignKeyConstraint(['session_id'], ['cotisation_sessions.id']),
        sa.ForeignKeyConstraint(['tontine_id'], ['tontines.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('idx_notification_user', 'notifications', ['user_id'])
    op.create_index('idx_notification_type', 'notifications', ['type'])
    op.create_index('idx_notification_status', 'notifications', ['status'])
    op.create_index('idx_notification_channel', 'notifications', ['channel'])
    op.create_index('idx_notification_scheduled', 'notifications', ['scheduled_at'])
    op.create_index('idx_notification_user_unread', 'notifications', ['user_id', 'status'])
    op.create_index('idx_notification_tontine', 'notifications', ['tontine_id'])


def downgrade() -> None:
    # Supprimer les tables dans l'ordre inverse
    op.drop_table('notifications')
    op.drop_table('passages')
    op.drop_table('payments')
    op.drop_table('cotisation_sessions')
    op.drop_table('tontine_members')
    op.drop_table('tontines')
    op.drop_table('users')
    
    # Supprimer les types ENUM
    op.execute("DROP TYPE IF EXISTS notificationstatus")
    op.execute("DROP TYPE IF EXISTS notificationchannel")
    op.execute("DROP TYPE IF EXISTS notificationtype")
    op.execute("DROP TYPE IF EXISTS passagestatus")
    op.execute("DROP TYPE IF EXISTS paymentmethod")
    op.execute("DROP TYPE IF EXISTS paymentstatus")
    op.execute("DROP TYPE IF EXISTS sessionstatus")
    op.execute("DROP TYPE IF EXISTS tontinefrequency")
    op.execute("DROP TYPE IF EXISTS tontinetype")
    op.execute("DROP TYPE IF EXISTS userrole")

