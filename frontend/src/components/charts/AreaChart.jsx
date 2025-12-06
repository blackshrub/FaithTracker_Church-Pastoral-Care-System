
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend
} from 'chart.js';

// Register components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Filler,
  Legend
);

export const AreaChart = ({ data, color = 'rgb(20, 184, 166)', dataKey, height = 300, formatValue }) => {
  const chartData = {
    labels: data.map(item => item.month || item.name),
    datasets: [
      {
        label: dataKey,
        data: data.map(item => item[dataKey] || item.value),
        fill: true,
        backgroundColor: color.replace('rgb', 'rgba').replace(')', ', 0.3)'),
        borderColor: color,
        tension: 0.4,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: function(context) {
            return formatValue ? formatValue(context.parsed.y) : context.parsed.y;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
      },
    },
  };

  return (
    <div style={{ height: `${height}px` }}>
      <Line data={chartData} options={options} />
    </div>
  );
};

export default AreaChart;
