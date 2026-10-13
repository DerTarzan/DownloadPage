"""Initiales Schema: users, user_sessions, categories, products, documents, settings

Revision ID: 0001_initial
Revises: 
Create Date: 2026-10-02 19:44:50.030994

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('categories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('image_path', sa.String(length=512), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_categories_slug'), 'categories', ['slug'], unique=True)
    op.create_index(op.f('ix_categories_sort_order'), 'categories', ['sort_order'], unique=False)
    op.create_table('settings',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('key', sa.String(length=100), nullable=False),
    sa.Column('value', sa.Text(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_settings_key'), 'settings', ['key'], unique=True)
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=64), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('is_admin', sa.Boolean(), server_default=sa.false(), nullable=False),
    sa.Column('is_active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('last_login', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_username'), 'users', ['username'], unique=True)
    op.create_table('products',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('category_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('slug', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('image_path', sa.String(length=512), nullable=True),
    sa.Column('sort_order', sa.Integer(), server_default='0', nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('category_id', 'slug', name='uq_products_category_slug')
    )
    op.create_index(op.f('ix_products_category_id'), 'products', ['category_id'], unique=False)
    op.create_table('user_sessions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('csrf_token', sa.String(length=64), nullable=False),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_user_sessions_expires_at'), 'user_sessions', ['expires_at'], unique=False)
    op.create_index(op.f('ix_user_sessions_token_hash'), 'user_sessions', ['token_hash'], unique=True)
    op.create_index(op.f('ix_user_sessions_user_id'), 'user_sessions', ['user_id'], unique=False)
    op.create_table('documents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('product_id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('original_filename', sa.String(length=255), nullable=False),
    sa.Column('storage_path', sa.String(length=512), nullable=False),
    sa.Column('mime_type', sa.String(length=100), nullable=False),
    sa.Column('file_size', sa.BigInteger(), nullable=False),
    sa.Column('checksum_sha256', sa.String(length=64), nullable=True),
    sa.Column('version', sa.String(length=32), server_default='1.0', nullable=False),
    sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
    sa.Column('uploaded_by', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['uploaded_by'], ['users.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('storage_path')
    )
    op.create_index(op.f('ix_documents_product_id'), 'documents', ['product_id'], unique=False)

    settings_table = sa.table("settings", sa.column("key", sa.String), sa.column("value", sa.Text))
    op.bulk_insert(
        settings_table,
        [
            {"key": "maintenance_mode", "value": "false"},
            {"key": "maintenance_message", "value": "Die Website befindet sich derzeit im Wartungsmodus. Bitte versuchen Sie es später erneut."},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_documents_product_id'), table_name='documents')
    op.drop_table('documents')
    op.drop_index(op.f('ix_user_sessions_user_id'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_token_hash'), table_name='user_sessions')
    op.drop_index(op.f('ix_user_sessions_expires_at'), table_name='user_sessions')
    op.drop_table('user_sessions')
    op.drop_index(op.f('ix_products_category_id'), table_name='products')
    op.drop_table('products')
    op.drop_index(op.f('ix_users_username'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_settings_key'), table_name='settings')
    op.drop_table('settings')
    op.drop_index(op.f('ix_categories_sort_order'), table_name='categories')
    op.drop_index(op.f('ix_categories_slug'), table_name='categories')
    op.drop_table('categories')
