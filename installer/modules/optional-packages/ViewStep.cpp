#include "ViewStep.h"
#include "GlobalStorage.h"
#include "JobQueue.h"
#include "Job.h"
#include "utils/Logger.h"

OptionalPackagesViewStep::OptionalPackagesViewStep( QObject* parent )
    : Calamares::ViewStep( parent )
    , m_page( new OptionalPackagesPage() )
{
}

OptionalPackagesViewStep::~OptionalPackagesViewStep() = default;

QString OptionalPackagesViewStep::prettyName() const
{
    return tr( "Optional packages" );
}

QString OptionalPackagesViewStep::prettyStatus() const
{
    return tr( "Installing optional packages..." );
}

QWidget* OptionalPackagesViewStep::widget()
{
    return m_page;
}

// Single-page step: next/back navigation is not used.
void OptionalPackagesViewStep::next() {}
void OptionalPackagesViewStep::back() {}

bool OptionalPackagesViewStep::isNextEnabled() const
{
    return true;
}

bool OptionalPackagesViewStep::isBackEnabled() const
{
    return true;
}

bool OptionalPackagesViewStep::isAtBeginning() const
{
    return true;
}

bool OptionalPackagesViewStep::isAtEnd() const
{
    return true;
}

void OptionalPackagesViewStep::onActivate()
{
    // Nothing to prepare when the page becomes visible.
}

void OptionalPackagesViewStep::onLeave()
{
    // Persist the user's selection to Calamares global storage so that a
    // subsequent job (e.g. a chroot shell script) can install the packages.
    const QStringList selected = m_page->selectedIds();
    Calamares::JobQueue::instance()->globalStorage()->insert( "optional-packages", selected );
    cDebug() << "Selected optional packages:" << selected;
}

Calamares::JobList OptionalPackagesViewStep::jobs() const
{
    // This step does not create jobs itself; it only stores the selection.
    return Calamares::JobList();
}

CALAMARES_PLUGIN_FACTORY_DEFINITION( OptionalPackagesPluginFactory, registerPlugin< OptionalPackagesViewStep >() )

void OptionalPackagesViewStep::setConfigurationMap( const QVariantMap& configurationMap )
{
    // Parse the "groups" list from the module configuration.
    const QVariantList groups = configurationMap.value( "groups" ).toList();
    for ( const QVariant& gv : groups )
    {
        const QVariantMap gm = gv.toMap();
        AptGroup group;
        group.id = gm.value( "id" ).toString();
        group.name = gm.value( "name" ).toString();
        group.description = gm.value( "description" ).toString();
        group.selected = gm.value( "selected" ).toBool();

        // Parse the "packages" list inside each group.
        const QVariantList packages = gm.value( "packages" ).toList();
        for ( const QVariant& pv : packages )
        {
            const QVariantMap pm = pv.toMap();
            AptPackage pkg;
            pkg.id = pm.value( "id" ).toString();
            pkg.name = pm.value( "name" ).toString();
            pkg.description = pm.value( "description" ).toString();
            pkg.package = pm.value( "package" ).toString();
            group.packages.append( pkg );
        }
        m_groups.append( group );
    }

    // Populate the UI with the parsed groups.
    m_page->setGroups( m_groups );
}
