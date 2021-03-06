================
Invoice Scenario
================

Imports::
    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install account_invoice::

    >>> config = activate_modules(['aeat_347', 'account_es'])

Create company::

    >>> eur = get_currency('EUR')
    >>> _ = create_company(currency=eur)
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create tax::

    >>> tax = create_tax(Decimal('.10'))
    >>> tax.operation_347 = 'base_amount'
    >>> tax.save()
    >>> tax2 = create_tax(Decimal('.10'))
    >>> tax2.operation_347 = 'base_amount'
    >>> tax2.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> identifier = party.identifiers.new()
    >>> identifier.type = 'eu_vat'
    >>> identifier.code = 'ES00000000T'
    >>> party.save()
    >>> party2 = Party(name='Party 2')
    >>> identifier = party2.identifiers.new()
    >>> identifier.type = 'eu_vat'
    >>> identifier.code = 'ES00000001R'
    >>> party2.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.customer_taxes.append(tax)
    >>> account_category.supplier_taxes.append(tax2)
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal('25')
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create out invoice over limit::

    >>> Record = Model.get('aeat.347.record')
    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.unit_price = Decimal(40)
    >>> line.quantity = 80
    >>> len(line.taxes)
    1
    >>> line.amount == Decimal('3200.00')
    True
    >>> invoice.click('post')
    >>> rec1, = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name
    'Party'
    >>> rec1.party_vat
    '00000000T'
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key
    'B'
    >>> rec1.amount == Decimal('3520.00')
    True

Create out invoice not over limit::

    >>> invoice = Invoice()
    >>> invoice.party = party2
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.unit_price = Decimal(40)
    >>> line.quantity = 5
    >>> len(line.taxes)
    1
    >>> line.amount == Decimal('200.00')
    True
    >>> invoice.click('post')
    >>> rec1, = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name
    'Party 2'
    >>> rec1.party_vat
    '00000001R'
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key
    'B'
    >>> rec1.amount == Decimal('220.00')
    True

Create out credit note::

    >>> invoice = Invoice()
    >>> invoice.type = 'out'
    >>> invoice.party = party
    >>> invoice.payment_term = payment_term
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.unit_price = Decimal(40)
    >>> line.quantity = -2
    >>> len(line.taxes)
    1
    >>> line.amount == Decimal('-80.00')
    True
    >>> invoice.click('post')
    >>> rec1, = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name
    'Party'
    >>> rec1.party_vat
    '00000000T'
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key
    'B'
    >>> rec1.amount == Decimal('-88.00')
    True

Create in invoice::

    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> invoice.type = 'in'
    >>> invoice.aeat347_operation_key = 'A'
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('25')
    >>> len(line.taxes)
    1
    >>> line.amount == Decimal('125.00')
    True
    >>> invoice.click('post')
    >>> rec1, = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name
    'Party'
    >>> rec1.party_vat
    '00000000T'
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key
    'A'
    >>> rec1.amount == Decimal('137.50')
    True

Create in credit note::

    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.aeat347_operation_key = 'A'
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.unit_price = Decimal('25.00')
    >>> line.quantity = -1
    >>> len(line.taxes)
    1
    >>> line.amount == Decimal('-25.00')
    True
    >>> invoice.click('post')
    >>> rec1, = Record.find([('invoice', '=', invoice.id)])
    >>> rec1.party_name
    'Party'
    >>> rec1.party_vat
    '00000000T'
    >>> rec1.month == today.month
    True
    >>> rec1.operation_key
    'A'
    >>> rec1.amount == Decimal('-27.50')
    True

Generate 347 Report::

    >>> Report = Model.get('aeat.347.report')
    >>> report = Report()
    >>> report.fiscalyear = fiscalyear
    >>> report.fiscalyear_code = 2013
    >>> report.company_vat = '123456789'
    >>> report.contact_name = 'Guido van Rosum'
    >>> report.contact_phone = '987654321'
    >>> report.representative_vat = '22334455'
    >>> report.click('calculate')
    >>> report.reload()
    >>> report.property_count
    0
    >>> report.party_count
    1
    >>> report.party_amount == Decimal('3432.00')
    True
    >>> report.cash_amount == Decimal('0.0')
    True
    >>> report.property_amount == Decimal('0.0')
    True

Reassign 347 lines::

    >>> reasign = Wizard('aeat.347.reasign.records', models=[invoice])
    >>> reasign.execute('reasign')
    >>> invoice.reload()
    >>> invoice.aeat347_operation_key
