"""empty message

Revision ID: dffc27647093
Revises: 93c4bc14aa22
Create Date: 2023-03-07 11:34:35.938189

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'dffc27647093'
down_revision = '93c4bc14aa22'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('report',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('item', sa.Integer(), nullable=True),
    sa.Column('type', sa.String(length=256), nullable=True),
    sa.Column('user', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('search_tree',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('folder', sa.Integer(), nullable=True),
    sa.Column('json', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['folder'], ['folder.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('search_tree')
    op.drop_table('report')
    # ### end Alembic commands ###
