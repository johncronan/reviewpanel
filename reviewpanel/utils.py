from formative.utils import TabularExport

from .models import Score


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
