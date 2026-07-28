from miyano_portal.setup.install_notifications import install_portal_notifications


def execute():
    # Re-trigger the (idempotent) installer so the notifications added after
    # the original patch (reject / delivery / invoice) get installed on
    # sites that already ran install_portal_notifications once.
    install_portal_notifications()
