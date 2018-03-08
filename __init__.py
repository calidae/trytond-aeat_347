#The COPYRIGHT file at the top level of this repository contains the full
#copyright notices and license terms.
from trytond.pool import Pool
from . import aeat, invoice, party, tax


def register():
    Pool.register(
        party.Party,
        aeat.Report,
        aeat.PartyRecord,
        aeat.PropertyRecord,
        invoice.Record,
        invoice.Invoice,
        invoice.Recalculate347RecordStart,
        invoice.Recalculate347RecordEnd,
        invoice.Reasign347RecordStart,
        invoice.Reasign347RecordEnd,
        invoice.InvoiceTax,
        tax.TaxTemplate,
        tax.Tax,
        module='aeat_347', type_='model')
    Pool.register(
        invoice.Recalculate347Record,
        invoice.Reasign347Record,
        module='aeat_347', type_='wizard')
