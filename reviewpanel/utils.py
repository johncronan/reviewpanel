from django.db.models import Subquery
from django.http import HttpResponse
from reportlab.pdfgen import canvas as pdfgen_canvas
from reportlab.lib import units, styles
from reportlab import platypus
from urllib.parse import quote
from itertools import groupby
import re

from formative.utils import TabularExport
from .models import Score, Input, Metric
from .templatetags.submission import dereference_block


class MetricsTabularExport(TabularExport):
    def __init__(self, filename, program_form, queryset, **kwargs):
        super().__init__(filename, program_form, queryset, **kwargs)
        self.metrics, self.inputs = [], []
        
        for name in self.args:
            if not self.args[name]: continue
            if name.startswith('metric_'): self.metrics.append(name)
            elif name.startswith('input_') and self.args[name][0] != 'no':
                self.inputs.append(name[len('input_'):])
        
        if self.inputs:
            self.text_scores = {}
            qs = Score.objects.filter(object_id__in=queryset.values('pk'))
            scores = qs.filter(input__name__in=self.inputs)
            for score in scores.order_by('created'):
                app = self.text_scores.setdefault(score.object_id, [])
                app.append(score.text)
    
    def header_row(self):
        row = super().header_row()
        
        for name in self.metrics: row.append(name)
        for name in self.inputs: row.append(name)
        return row
    
    def data_row(self, submission, sub_items):
        row = super().data_row(submission, sub_items)
        
        def field_val(item, field):
            val = getattr(item, field)
            if val is None: return ''
            return val
        
        for name in self.metrics: row.append(field_val(submission, name))
        for name in self.inputs:
            vals = []
            if submission.pk in self.text_scores:
                vals = self.text_scores[submission.pk]
            row.append("\n".join(vals))
        
        return row


class PresentationPrintExport:
    def __init__(self, filename, presentation, **kwargs):
        self.filename, self.args = filename, kwargs
        self.presentation = presentation
        self.orientation = kwargs['orientation']
        self.styles = styles.getSampleStyleSheet()
        
        qs = Metric.objects.filter(input__form=presentation.form,
                                   display_values=True).select_related('input')
        vals_metrics = { f'metric_{m.input.name}_{m.name}': m for m in qs }
        
        self.metrics, self.vals_metrics = {}, {}
        for name in self.args:
            if not self.args[name] or not name.startswith('metric_'): continue
            if name in vals_metrics:
                self.vals_metrics[name] = vals_metrics[name]
            else: self.metrics[name] = True
        
        self.sections = {}
        for sec in presentation.template.sections.filter(h__isnull=False):
            self.sections[sec.name] = (float(sec.x)/100, float(sec.y)/100,
                                       float(sec.w)/100, float(sec.h)/100,
                                       sec.font)
        refs = presentation.references
        self.references = refs.select_related('section').order_by('_rank')
        names = Subquery(self.references.filter(collection='').values('name'))
        self.blocks = { b.name: b for b
                        in presentation.form.blocks.filter(name__in=names) }
    
    def apps_per_page(self, canvas):
        # TODO
        return 2
    
    def font_info(self, font_str):
        strs = font_str.split()
        if len(strs) < 2: return 12, 'sans-serif'
        size_str, family = strs[-2:]
        match = re.match(r'^([0-9.-]+)(.*)$', size_str)
        if not match: return 12, family
        size, unit = match.groups()
        units = {'': 1, 'pt': 1, 'px': 0.75, '%': 0.12, 'em': 12}
        try: value = float(size) * units[unit]
        except KeyError: return 12, family
        return value, family # TODO map family to PDF standard font names
    
    def render_app(self, app, x0, y0, dx, dy, c):
        content = {}
        for ref in self.references:
            if ref.collection: continue # TODO
            section = content.setdefault(ref.section.name, [])
            blabel, ilabel = ref.block_label, ref.inline_label
            val = dereference_block({'blocks': self.blocks}, ref, app)
            section.append(((blabel, ilabel), val))
        
        for sec_name, vals in content.items():
            x, y, w, h, font = self.sections[sec_name]
            style = self.styles['BodyText']
            style.fontSize, _ = self.font_info(font)
            left, top, width, height = x0 + x*dx, y0 - y*dx, w*dx, h*dx
            frame = platypus.Frame(left, top - height, width, height)
            pars = []
            for (blabel, ilabel), val in vals:
                if blabel: pars.append(platypus.Paragraph(blabel, style))
                if ilabel: ilabel += ' '
                par = platypus.Paragraph(ilabel + val, style)
                pars.append(platypus.KeepInFrame(0, 0, [par]))
            frame.addFromList(pars, c)
        
        metrics_name = self.presentation.metrics_section()
        if metrics_name in self.sections:
            x, y, w, h, font = self.sections[metrics_name]
            size, _ = self.font_info(font)
            c.setFontSize(size)
            
            left, top, width, height = x0 + x*dx, y0 - y*dx, w*dx, h*dx
            metrics_h, metric_w = 20, width / len(self.metrics)
            for i, name in enumerate(self.metrics):
                l = left + i * metric_w
                label = name[len('metric_'):].replace('_', ' ')
                val = getattr(app, name)
                if val is None: val = ''
                elif type(val) not in (int, bool): val = f'{val:.3f}'
                c.drawString(l, top, f'{label}: {val}')
            
            vals_h = height / len(self.vals_metrics)
            for i, name in enumerate(self.vals_metrics):
                t = top - metrics_h - i * vals_h
                if app.pk not in self.values[name]: continue
                
                for j, score in enumerate(self.values[name][app.pk]):
                    val, input = str(score.value), self.vals_metrics[name].input
                    if input.type == Input.InputType.TEXT: val = score.text
                    c.drawString(left, t - j*1.3*size, val) # TODO: KeepInFrame
    
    def render_pages(self, queryset, canvas):
        num = self.apps_per_page(canvas)
        height = 11 * units.inch
        incr = height / num
        
        page, i = 1, 0
        for app in queryset:
            y = height - (i % num) * incr - 0
            if i and not (i % num):
                canvas.showPage()
                page += 1
            
            self.render_app(app, 50, y, 8.5 * units.inch - 100, incr, canvas)
            
            if not (i % num):
                canvas.setFontSize(8)
                canvas.drawString(4.25*units.inch, 28, str(page))
            i += 1
        canvas.showPage()
    
    def response(self, queryset):
        self.values = {}
        for name, metric in self.vals_metrics.items():
            subq = Subquery(queryset.values('pk'))
            qs = Score.objects.filter(object_id__in=subq, input=metric.input)
            if metric.cohort: qs = qs.filter(cohort=metric.cohort)
            scores = qs.order_by('object_id', 'created')
            objects = groupby(scores, key=lambda s: s.object_id)
            self.values[name] = { k: list(vals) for k, vals in objects }
        
        response = HttpResponse(content_type='application/pdf')
        canvas = pdfgen_canvas.Canvas(response)
        self.render_pages(queryset, canvas)
        
        canvas.save()
        disp = f"attachment; filename*=UTF-8''" + quote(self.filename)
        response['Content-Disposition'] = disp
        return response
