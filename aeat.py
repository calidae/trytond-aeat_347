# -*- coding: utf-8 -*-
import itertools
import datetime
from decimal import Decimal
from retrofix import aeat347
import retrofix
import unicodedata

from trytond.model import Workflow, ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.pyson import Eval
from trytond.transaction import Transaction

__all__ = ['Report', 'PartyRecord', 'PropertyRecord']

_ZERO = Decimal('0.0')

OPERATION_KEY = [
    ('A', 'A - Good and service adquisitions above limit (1)'),
    ('B', 'B - Good and service deliveries above limit (1)'),
    ('C', 'C - Money collection on behavlf of third parties above '
        'limit (3)'),
    ('D', 'D - Adquisitions by Public Institutions (...) above '
        'limit (1)'),
    ('E', 'E - Grants and help made by public institutions above limit '
        '(1)'),
    ('F', 'F - Travel Agency Sales'),
    ('G', 'G - Travel Agency Purchases'),
    ]

src_chars = """àáäâÀÁÄÂèéëêÈÉËÊìíïîÌÍÏÎòóöôÒÓÖÔùúüûÙÚÜÛçñºª·¤ '"()/*-+?!&$[]{}@#`'^:;<>=~%\\"""
src_chars = unicode(src_chars, 'iso-8859-1')
dst_chars = """aaaaAAAAeeeeEEEEiiiiIIIIooooOOOOuuuuUUUUcnoa.e______________________________"""
dst_chars = unicode(dst_chars, 'iso-8859-1')


def unaccent(text):
    if isinstance(text, str):
        text = unicode(text, 'utf-8')
    return unicodedata.normalize('NFKD', text).encode('ASCII', 'ignore')


class Report(Workflow, ModelSQL, ModelView):
    'AEAT 347 Report'
    __name__ = "aeat.347.report"
    _rec_name = "number"

    company = fields.Many2One('company.company', 'Company', required=True,
        states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    currency = fields.Function(fields.Many2One('currency.currency',
        'Currency'), 'get_currency')
    previous_number = fields.Char('Previous Declaration Number', size=13,
        states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    representative_vat = fields.Char('L.R. VAT number', size=9,
        help='Legal Representative VAT number.', states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    fiscalyear = fields.Many2One('account.fiscalyear', 'Fiscal Year',
        required=True, states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    fiscalyear_code = fields.Integer('Fiscal Year Code', required=True)
    company_vat = fields.Char('VAT number', size=9, states={
            'required': True,
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    type = fields.Selection([
            ('N', 'Normal'),
            ('C', 'Complementary'),
            ('S', 'Substitutive')
            ], 'Statement Type', required=True, states={
                'readonly': Eval('state') == 'done',
            }, depends=['state'])
    support_type = fields.Selection([
            ('C', 'DVD'),
            ('T', 'Telematics'),
            ], 'Support Type', required=True, states={
                'readonly': Eval('state') == 'done',
            }, depends=['state'])
    calculation_date = fields.DateTime('Calculation Date')
    state = fields.Selection([
            ('draft', 'Draft'),
            ('calculated', 'Calculated'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled')
            ], 'State', readonly=True)
    contact_name = fields.Char('Full Name', size=40)
    contact_phone = fields.Char('Phone', size=9)
    group_by_vat = fields.Boolean('Group by VAT', states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    operation_limit = fields.Numeric('Invoiced Limit (1)', digits=(16, 2),
        required=True, help='The declaration will include parties with the '
        'total of operations over this limit')
    received_cash_limit = fields.Numeric('Received Cash Limit (2)',
        digits=(16, 2), required=True, help='The declaration will show the '
        'total of cash operations over this limit')
    on_behalf_third_party_limit = fields.Numeric('On Behalf of Third '
        'Party Limit (3)', digits=(16, 2), required=True,
        help='The declaration will include parties from which we received '
        'payments, on behalf of third parties, over this limit')
    amount = fields.Function(fields.Numeric('Amount', digits=(16, 2)),
        'get_totals')
    cash_amount = fields.Function(fields.Numeric('Cash Amount (Manual)',
            digits=(16, 2)), 'get_totals')
    party_amount = fields.Function(fields.Numeric(
            'Party Amount', digits=(16, 2)), 'get_totals')
    party_count = fields.Function(fields.Integer('Party Record Count'),
        'get_totals')
    property_amount = fields.Function(fields.Numeric(
            'Property Amount', digits=(16, 2)), 'get_totals')
    property_count = fields.Function(fields.Integer(
            'Property Record Count'), 'get_totals')
    parties = fields.One2Many('aeat.347.report.party', 'report',
        'Party Records', states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    properties = fields.One2Many('aeat.347.report.property', 'report',
        'Property Records', states={
            'readonly': Eval('state') == 'done',
            }, depends=['state'])
    file_ = fields.Binary('File', states={
            'invisible': Eval('state') != 'done',
            })

    @classmethod
    def __setup__(cls):
        super(Report, cls).__setup__()
        cls._error_messages.update({
                'invalid_currency': ('Currency in AEAT 340 report "%s" must be'
                    ' Euro.'),
                })
        cls._buttons.update({
                'draft': {
                    'invisible': ~Eval('state').in_(['calculated',
                            'cancelled']),
                    },
                'calculate': {
                    'invisible': ~Eval('state').in_(['draft']),
                    },
                'process': {
                    'invisible': ~Eval('state').in_(['calculated']),
                    },
                'cancel': {
                    'invisible': Eval('state').in_(['cancelled']),
                    },
                })
        cls._transitions |= set((
                ('draft', 'calculated'),
                ('draft', 'cancelled'),
                ('calculated', 'draft'),
                ('calculated', 'done'),
                ('calculated', 'cancelled'),
                ('done', 'cancelled'),
                ('cancelled', 'draft'),
                ))

    @staticmethod
    def default_operation_limit():
        return Decimal('3005.06')

    @staticmethod
    def default_on_behalf_third_party_limit():
        return Decimal('300.51')

    @staticmethod
    def default_received_cash_limit():
        return Decimal('6000.00')

    @staticmethod
    def default_type():
        return 'N'

    @staticmethod
    def default_support_type():
        return 'T'

    @staticmethod
    def default_state():
        return 'draft'

    @staticmethod
    def default_group_by_vat():
        return True

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    @staticmethod
    def default_fiscalyear():
        FiscalYear = Pool().get('account.fiscalyear')
        return FiscalYear.find(
            Transaction().context.get('company'), exception=False)

    def get_rec_name(self, name):
        return '%s - %s' % (self.company.rec_name,
            self.fiscalyear.name)

    def get_currency(self, name):
        return self.company.currency.id

    @fields.depends('fiscalyear')
    def on_change_with_fiscalyear_code(self):
        code = None
        if self.fiscalyear:
            code = self.fiscalyear.start_date.year
        return code

    @classmethod
    def get_totals(cls, reports, names):
        res = {}
        for name in ('party_count', 'property_count'):
            res[name] = dict.fromkeys([x.id for x in reports], 0)
        for name in ('party_amount', 'cash_amount', 'property_amount'):
            res[name] = dict.fromkeys([x.id for x in reports], _ZERO)
        for report in reports:
            res['party_amount'][report.id] = sum([x.amount for x in
                    report.parties]) or Decimal('0.0')
            res['party_count'][report.id] = len(report.parties)
            res['cash_amount'][report.id] = sum([x.cash_amount for x in
                    report.parties]) or Decimal('0.0')
            res['property_amount'][report.id] = sum([x.amount for x in
                    report.properties]) or Decimal('0.0')
            res['property_count'][report.id] = len(report.properties)
        for key in res.keys():
            if key not in names:
                del res[key]
        return res

    @classmethod
    def validate(cls, reports):
        for report in reports:
            report.check_euro()

    def check_euro(self):
        if self.currency.code != 'EUR':
            self.raise_user_error('invalid_currency', self.rec_name)

    @classmethod
    @ModelView.button
    @Workflow.transition('calculated')
    def calculate(cls, reports):
        pool = Pool()
        Data = pool.get('aeat.347.record')
        Operation = pool.get('aeat.347.report.party')

        quarter_mapping = [(3, 'first'), (6, 'second'), (9, 'third'),
            (12, 'fourth')]

        with Transaction().set_user(0):
            Operation.delete(Operation.search([
                ('report', 'in', [r.id for r in reports])]))

        for report in reports:
            fiscalyear = report.fiscalyear

            to_create = {}
            for record in Data.search([('fiscalyear', '=', fiscalyear.id)]):

                key = '%s-%s-%s' % (report.id, record.party.id,
                    record.operation_key)

                if key in to_create:
                    for month, quarter in quarter_mapping:
                        if month >= record.month:
                            break
                    qkey = "%s_quarter_amount" % quarter
                    to_create[key]['amount'] += record.amount
                    to_create[key][qkey] += record.amount
                    to_create[key]['records'][0][1].append(record.id)
                else:
                    to_create[key] = {
                        'amount': record.amount,
                        'cash_amount': _ZERO,
                        'party_vat': record.party_vat[:9],
                        'party_name': record.party_name,
                        'country_code': record.country_code,
                        'province_code': record.province_code,
                        'operation_key': record.operation_key,
                        'report': report.id,
                        'records': [('add', [(record.id)])],
                    }
                    saved = False
                    for month, quarter in quarter_mapping:
                        qkey = "%s_quarter_amount" % quarter
                        if not qkey in to_create[key]:
                            to_create[key][qkey] = _ZERO

                        if month >= record.month and not saved:
                            to_create[key][qkey] += record.amount
                            saved = True
                        qkey = "%s_quarter_property_amount" % quarter
                        to_create[key][qkey] = _ZERO

            for key, record in to_create.copy().iteritems():
                amount = record['amount']
                cash_amount = record['cash_amount']
                if not (amount > report.operation_limit or
                        cash_amount > report.received_cash_limit):
                    del to_create[key]
        with Transaction().set_user(0, set_context=True):
            Operation.create(to_create.values())
        cls.write(reports, {
                'calculation_date': datetime.datetime.now(),
                })

    @classmethod
    @ModelView.button
    @Workflow.transition('done')
    def process(cls, reports):
        for report in reports:
            report.create_file()

    @classmethod
    @ModelView.button
    @Workflow.transition('cancelled')
    def cancel(cls, reports):
        pass

    @classmethod
    @ModelView.button
    @Workflow.transition('draft')
    def draft(cls, reports):
        pass

    def create_file(self):
        records = []
        record = retrofix.Record(aeat347.PRESENTER_HEADER_RECORD)
        record.fiscalyear = str(self.fiscalyear_code)
        record.nif = self.company_vat
        record.presenter_name = unaccent(self.company.party.name)
        record.support_type = self.support_type
        record.contact_phone = self.contact_phone
        record.contact_name = unaccent(self.contact_name)
        record.declaration_number = str(self.id)
        #record.complementary =
        #record.replacement =
        record.previous_declaration_number = self.previous_number
        record.party_count = len(self.parties)
        record.party_amount = self.party_amount
        record.property_count = len(self.properties)
        record.property_amount = self.property_amount or Decimal('0.0')
        record.representative_nif = self.representative_vat
        records.append(record)
        for line in itertools.chain(self.parties, self.properties):
            record = line.get_record()
            record.fiscalyear = str(self.fiscalyear_code)
            record.nif = self.company_vat
            records.append(record)
        data = retrofix.record.write(records)
        self.file_ = buffer(data)
        self.save()


class PartyRecord(ModelSQL, ModelView):
    """
    AEAT 347 Party Record
    """
    __name__ = 'aeat.347.report.party'
    _rec_name = "party_vat"

    company = fields.Many2One('company.company', 'Company', required=True)
    report = fields.Many2One('aeat.347.report', 'AEAT 347 Report',
        ondelete='CASCADE', select=1)
    party_name = fields.Char('Party Name', size=40)
    party_vat = fields.Char('VAT', size=9)
    representative_vat = fields.Char('L.R. VAT number', size=9,
        help='Legal Representative VAT number')
    province_code = fields.Char('Province Code', size=2)
    country_code = fields.Char('Country Code', size=2)
    operation_key = fields.Selection(OPERATION_KEY, 'Operation Key')
    amount = fields.Numeric('Operations Amount', digits=(16, 2))
    insurance = fields.Boolean('Insurance Operation', help='Only for '
        'insurance companies. Set to identify insurance operations aside from '
        'the rest.')
    business_premises_rent = fields.Boolean('Bussiness Premises Rent',
        help='Set to identify premises rent operations aside from the rest. '
        'You\'ll need to fill in the premises info only when you are the one '
        'that receives the money.')
    cash_amount = fields.Numeric('Cash Amount Received', digits=(16, 2))
    property_amount = fields.Numeric('VAT Liable Property Amount',
        digits=(16, 2))
    fiscalyear_code_cash_operation = fields.Integer(
        'Fiscal Year Cash Operation')
    first_quarter_amount = fields.Numeric('First Quarter Amount',
        digits=(16, 2))
    first_quarter_property_amount = fields.Numeric('First '
        'Quarter Property Amount', digits=(16, 2))
    second_quarter_amount = fields.Numeric('Second Quarter Amount',
        digits=(16, 2))
    second_quarter_property_amount = fields.Numeric('Second '
        'Quarter Property Amount', digits=(16, 2))
    third_quarter_amount = fields.Numeric('Third Quarter Amount',
        digits=(16, 2))
    third_quarter_property_amount = fields.Numeric('Third '
        'Quarter Property Amount', digits=(16, 2))
    fourth_quarter_amount = fields.Numeric('Fourth Quarter Amount',
        digits=(16, 2))
    fourth_quarter_property_amount = fields.Numeric('Fourth '
        'Quarter Property Amount', digits=(16, 2))
    records = fields.One2Many('aeat.347.record', 'party_record',
        'AEAT 347 Records', readonly=True)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_record(self):
        record = retrofix.Record(aeat347.PARTY_RECORD)
        record.party_nif = self.party_vat
        record.representative_nif = self.representative_vat or ''
        record.party_name = unaccent(self.party_name)
        record.province_code = self.province_code
        if self.country_code == 'ES':
            record.country_code = ''
        else:
            record.country_code = self.country_code
        record.operation_key = self.operation_key
        record.amount = self.amount
        record.insurance = self.insurance
        record.business_premises_rent = self.business_premises_rent
        record.cash_amount = self.cash_amount or _ZERO
        record.vat_liable_property_amount = self.property_amount \
            or Decimal('0.0')
        record.fiscalyear_cash_operation = str(
            self.fiscalyear_code_cash_operation or '')
        record.first_quarter_amount = self.first_quarter_amount
        record.first_quarter_property_amount = (
            self.first_quarter_property_amount)
        record.second_quarter_amount = self.second_quarter_amount
        record.second_quarter_property_amount = (
            self.second_quarter_property_amount)
        record.third_quarter_amount = self.third_quarter_amount
        record.third_quarter_property_amount = (
            self.third_quarter_property_amount)
        record.fourth_quarter_amount = self.fourth_quarter_amount
        record.fourth_quarter_property_amount = (
            self.fourth_quarter_property_amount)
        return record


class PropertyRecord(ModelSQL, ModelView):
    """
    AEAT 347 Property Record
    """
    __name__ = 'aeat.347.report.property'
    _rec_name = "cadaster_number"

    company = fields.Many2One('company.company', 'Company', required=True)
    report = fields.Many2One('aeat.347.report', 'AEAT 347 Report',
        ondelete='CASCADE', select=1)
    party_vat = fields.Char('VAT number', size=9)
    representative_vat = fields.Char('L.R. VAT number', size=9,
        help='Legal Representative VAT number')
    party_name = fields.Char('Party Name', size=40)
    amount = fields.Numeric('Amount', digits=(16, 2))
    situation = fields.Selection([
            ('1', '1 - Spain but Basque Country and Navarra'),
            ('2', '2 - Basque Country and Navarra'),
            ('3', '3 - Spain, without catastral reference'),
            ('4', '4 - Foreign'),
            ], 'Property Situation', required=True)
    cadaster_number = fields.Char('Cadaster Reference', size=25)
    road_type = fields.Char('Road Type', size=5)
    street = fields.Char('Street', size=50)
    number_type = fields.Selection([
            ('NUM', 'Number'),
            ('KM.', 'Kilometer'),
            ('S/N', 'Without number'),
            ], 'Number type')
    number = fields.Integer('Number')
    number_qualifier = fields.Selection([
            ('BIS', 'Bis'),
            ('MOD', 'Mod'),
            ('DUP', 'Dup'),
            ('ANT', 'Ant'),
            ], 'Number Qualifier')
    block = fields.Char('Block', size=3)
    doorway = fields.Char('Doorway', size=3)
    stair = fields.Char('Stair', size=3)
    floor = fields.Char('Floor', size=3)
    door = fields.Char('Door', size=3)
    complement = fields.Char('Complement', size=40,
        help='Complement (urbanization, industrial park...)')
    city = fields.Char('City', size=30)
    municipality = fields.Char('Municipality', size=30)
    municipality_code = fields.Char('Municipality Code', size=5)
    province_code = fields.Char('Province Code', size=2)
    zip = fields.Char('Zip', size=5)

    @staticmethod
    def default_company():
        return Transaction().context.get('company')

    def get_record(self):
        record = retrofix.Record(aeat347.PROPERTY_RECORD)
        record.party_vat = self.party_vat
        record.representative_vat = self.representative_vat
        record.party_name = self.party_name
        record.amount = self.amount
        record.situation = self.situation
        record.cadaster_number = self.cadaster_number
        record.road_type = self.road_type
        record.street = self.street
        record.number_type = self.number_type
        record.number = self.number
        record.number_qualifier = self.number_qualifier
        record.block = self.block
        record.doorway = self.doorway
        record.stair = self.stair
        record.floor = self.floor
        record.door = self.door
        record.complement = self.complement
        record.city = self.city
        record.municipality = self.municipality
        record.municipality_code = self.municipality_code
        record.province_code = self.province_code
        record.zip = self.zip
        return record
