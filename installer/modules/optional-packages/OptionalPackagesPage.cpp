#include "OptionalPackagesPage.h"
#include <QVBoxLayout>
#include <QLabel>

/// Custom data role used to distinguish group items from package items.
static constexpr int RoleType = Qt::UserRole + 1;

OptionalPackagesPage::OptionalPackagesPage( QWidget* parent )
    : QWidget( parent )
    , m_tree( new QTreeWidget( this ) )
{
    auto* layout = new QVBoxLayout( this );
    layout->setContentsMargins( 16, 16, 16, 16 );
    layout->setSpacing( 12 );

    // Informative label shown above the package tree.
    auto* label = new QLabel( tr( "Select additional packages to install:" ) );
    label->setWordWrap( true );
    layout->addWidget( label );

    // Configure the tree to show only one column and hide the header.
    m_tree->setHeaderHidden( true );
    m_tree->setColumnCount( 1 );
    m_tree->setStyleSheet( QStringLiteral( "QTreeWidget::item { padding: 4px 0; }" ) );
    layout->addWidget( m_tree );

    connect( m_tree, &QTreeWidget::itemChanged, this, &OptionalPackagesPage::onItemChanged );
}

void OptionalPackagesPage::setGroups( const QVector< AptGroup >& groups )
{
    m_groups = groups;
    m_tree->clear();

    for ( const auto& group : groups )
    {
        // Create a top-level group item with a tristate checkbox.
        auto* groupItem = new QTreeWidgetItem( m_tree );
        groupItem->setText( 0, QString( "%1 — %2" ).arg( group.name, group.description ) );
        groupItem->setFlags( groupItem->flags() | Qt::ItemIsUserCheckable | Qt::ItemIsUserTristate );
        groupItem->setCheckState( 0, group.selected ? Qt::Checked : Qt::Unchecked );
        groupItem->setData( 0, Qt::UserRole, group.id );
        groupItem->setData( 0, RoleType, QStringLiteral( "group" ) );

        // Create a child item for each package in the group.
        for ( const auto& pkg : group.packages )
        {
            auto* pkgItem = new QTreeWidgetItem( groupItem );
            pkgItem->setText( 0, QString( "%1 — %2" ).arg( pkg.name, pkg.description ) );
            pkgItem->setFlags( pkgItem->flags() | Qt::ItemIsUserCheckable );
            pkgItem->setCheckState( 0, group.selected ? Qt::Checked : Qt::Unchecked );
            pkgItem->setData( 0, Qt::UserRole, pkg.id );
            pkgItem->setData( 0, RoleType, QStringLiteral( "package" ) );
            pkgItem->setToolTip( 0, pkg.package );
        }
    }

    m_tree->expandAll();
}

QStringList OptionalPackagesPage::selectedIds() const
{
    QStringList ids;

    // Iterate over all groups and collect checked package ids.
    for ( int i = 0; i < m_tree->topLevelItemCount(); ++i )
    {
        QTreeWidgetItem* groupItem = m_tree->topLevelItem( i );
        for ( int j = 0; j < groupItem->childCount(); ++j )
        {
            QTreeWidgetItem* pkgItem = groupItem->child( j );
            if ( pkgItem->checkState( 0 ) == Qt::Checked )
            {
                ids.append( pkgItem->data( 0, Qt::UserRole ).toString() );
            }
        }
    }

    return ids;
}

void OptionalPackagesPage::onItemChanged( QTreeWidgetItem* item, int column )
{
    // Only column 0 holds the checkbox, so ignore other columns.
    if ( column != 0 )
    {
        return;
    }

    const bool isGroup = item->data( 0, RoleType ).toString() == QStringLiteral( "group" );

    // Block signals while programmatically updating related items to avoid recursion.
    m_tree->blockSignals( true );

    if ( isGroup )
    {
        // Qt's tristate checkbox cycles Unchecked -> PartiallyChecked -> Checked.
        // For a group "select all" checkbox, PartiallyChecked should mean "check all children".
        Qt::CheckState state = item->checkState( 0 );
        if ( state == Qt::PartiallyChecked )
        {
            state = Qt::Checked;
            item->setCheckState( 0, Qt::Checked );
        }
        updateChildren( item, state );
    }
    else
    {
        updateParent( item );
    }

    m_tree->blockSignals( false );
}

void OptionalPackagesPage::updateChildren( QTreeWidgetItem* parent, Qt::CheckState state )
{
    for ( int i = 0; i < parent->childCount(); ++i )
    {
        parent->child( i )->setCheckState( 0, state );
    }
}

void OptionalPackagesPage::updateParent( QTreeWidgetItem* child )
{
    QTreeWidgetItem* parent = child->parent();
    if ( !parent )
    {
        return;
    }

    // Count checked and unchecked siblings to determine the parent state.
    int checked = 0;
    int unchecked = 0;
    for ( int i = 0; i < parent->childCount(); ++i )
    {
        Qt::CheckState state = parent->child( i )->checkState( 0 );
        if ( state == Qt::Checked )
        {
            ++checked;
        }
        else if ( state == Qt::Unchecked )
        {
            ++unchecked;
        }
    }

    if ( checked == parent->childCount() )
    {
        parent->setCheckState( 0, Qt::Checked );
    }
    else if ( unchecked == parent->childCount() )
    {
        parent->setCheckState( 0, Qt::Unchecked );
    }
    else
    {
        parent->setCheckState( 0, Qt::PartiallyChecked );
    }
}
