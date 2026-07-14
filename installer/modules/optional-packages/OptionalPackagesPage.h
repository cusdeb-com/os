#pragma once

#include <QWidget>
#include <QTreeWidget>
#include <QTreeWidgetItem>

/**
 * @brief Description of a single optional apt package.
 *
 * This struct holds the user-visible metadata and the underlying apt package
 * name for one package that can be selected on the optional packages page.
 */
struct AptPackage
{
    QString id;          ///< Internal identifier used to store the selection.
    QString name;        ///< Short user-visible name.
    QString description; ///< Longer user-visible description.
    QString package;     ///< Underlying apt package name (shown as tooltip).
};

/**
 * @brief Description of a group of optional apt packages.
 *
 * A group is rendered as a top-level checkable item in the tree. Selecting
 * a group toggles all of its child packages.
 */
struct AptGroup
{
    QString id;                   ///< Internal identifier for the group.
    QString name;                 ///< Short user-visible name.
    QString description;          ///< Longer user-visible description.
    bool selected;                ///< Initial selection state for the group and its packages.
    QVector< AptPackage > packages; ///< Packages belonging to this group.
};

/**
 * @brief Widget that lets the user select optional apt packages.
 *
 * Packages are presented in a tree grouped by category. Group checkboxes use
 * Qt's tristate support: checking a group checks all packages, unchecking it
 * unchecks them, and partially selected groups reflect mixed package states.
 */
class OptionalPackagesPage : public QWidget
{
    Q_OBJECT
public:
    /**
     * @brief Construct the page.
     * @param parent Optional parent widget.
     */
    explicit OptionalPackagesPage( QWidget* parent = nullptr );

    /**
     * @brief Populate the tree with groups and their packages.
     * @param groups List of package groups to display.
     */
    void setGroups( const QVector< AptGroup >& groups );

    /**
     * @brief Return the ids of all currently checked packages.
     * @return List of selected package ids.
     */
    QStringList selectedIds() const;

private slots:
    /**
     * @brief Handle changes to item check state in the tree.
     * @param item The item that changed.
     * @param column Column index that changed (only column 0 is relevant).
     */
    void onItemChanged( QTreeWidgetItem* item, int column );

private:
    /**
     * @brief Set the check state of all children of @p parent to @p state.
     * @param parent Group item whose children should be updated.
     * @param state New check state for all children.
     */
    void updateChildren( QTreeWidgetItem* parent, Qt::CheckState state );

    /**
     * @brief Recalculate the check state of @p child's parent based on siblings.
     * @param child Package item whose parent should be updated.
     */
    void updateParent( QTreeWidgetItem* child );

    QTreeWidget* m_tree;        ///< Tree widget showing groups and packages.
    QVector< AptGroup > m_groups; ///< Cached copy of the displayed groups.
};
