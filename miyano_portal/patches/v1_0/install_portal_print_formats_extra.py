from miyano_portal.setup.install_print_formats import install_portal_print_formats


def execute():
    # Re-trigger the (idempotent) installer so the two print formats added
    # after the original patch (Delivery Note, Sales Invoice) get installed
    # on sites that already ran install_portal_print_formats once.
    install_portal_print_formats()
