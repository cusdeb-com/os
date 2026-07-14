#pragma once

#include "OptionalPackagesPage.h"
#include "viewpages/ViewStep.h"
#include "utils/PluginFactory.h"
#include <QVariantMap>

// Calamares plugin factory declaration for the optional packages module.
CALAMARES_PLUGIN_FACTORY_DECLARATION( OptionalPackagesPluginFactory )

/**
 * @brief Calamares view step for selecting optional packages.
 *
 * This step presents a list of optional apt package groups to the user and
 * stores the selected package ids in Calamares global storage under the key
 * "optional-packages".
 */
class OptionalPackagesViewStep : public Calamares::ViewStep
{
    Q_OBJECT
public:
    /**
     * @brief Construct the view step.
     * @param parent Optional parent object.
     */
    explicit OptionalPackagesViewStep( QObject* parent = nullptr );

    /**
     * @brief Destroy the view step.
     */
    ~OptionalPackagesViewStep() override;

    /**
     * @brief Return the user-visible name of the step.
     * @return Localized step name.
     */
    QString prettyName() const override;

    /**
     * @brief Return the status text shown while this step is active.
     * @return Localized status text.
     */
    QString prettyStatus() const override;

    /**
     * @brief Return the widget displayed for this step.
     * @return Pointer to the OptionalPackagesPage widget.
     */
    QWidget* widget() override;

    // Navigation hooks (no-op for this single-page step).
    void next() override;
    void back() override;

    // Navigation state (both directions are always enabled).
    bool isNextEnabled() const override;
    bool isBackEnabled() const override;
    bool isAtBeginning() const override;
    bool isAtEnd() const override;

    // Lifecycle hooks.
    void onActivate() override;
    void onLeave() override;

    /**
     * @brief Return the list of jobs created by this step.
     * @return Empty list; this step only stores a selection for later jobs.
     */
    Calamares::JobList jobs() const override;

    /**
     * @brief Load package groups from the Calamares configuration map.
     * @param configurationMap Map parsed from the module's config file.
     */
    void setConfigurationMap( const QVariantMap& configurationMap ) override;

private:
    OptionalPackagesPage* m_page; ///< Widget shown by this view step.
    QVector< AptGroup > m_groups; ///< Parsed package groups from configuration.
};
