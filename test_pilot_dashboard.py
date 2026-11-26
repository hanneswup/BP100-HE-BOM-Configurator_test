import unittest

from pilot_dashboard import historical_performance_chart


class PilotDashboardTests(unittest.TestCase):
    def test_chart_uses_historical_metrics_and_90_percent_target(self):
        chart = historical_performance_chart({'precision': 0.675, 'recall': 0.588})
        spec = chart.to_dict()
        rows = [row for dataset in spec['datasets'].values() for row in dataset]
        self.assertIn({'Metric': 'Component precision', 'Percent': 67.5, 'Display': '67.5%'}, rows)
        self.assertIn({'Metric': 'Component completeness', 'Percent': 58.8, 'Display': '58.8%'}, rows)
        self.assertIn({'Target': 90}, rows)

    def test_unknown_or_invalid_metrics_do_not_become_zero(self):
        self.assertIsNone(historical_performance_chart({'precision': None, 'recall': float('nan')}))
        chart = historical_performance_chart({'precision': None, 'recall': 0.75})
        rows = [row for dataset in chart.to_dict()['datasets'].values() for row in dataset]
        self.assertFalse(any(row.get('Metric') == 'Component precision' for row in rows))
        self.assertTrue(any(row.get('Metric') == 'Component completeness' for row in rows))


if __name__ == '__main__':
    unittest.main()
