import {
  Box,
  Typography,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  LinearProgress,
} from '@mui/material';
import {
  Circle as CircleIcon,
} from '@mui/icons-material';

const getChargeColor = (level) => {
  if (level <= 20) return "error";
  if (level <= 50) return "warning";
  return "success";
};

const DeviceItem = ({ deviceId, data, onToggleSelect, onToggleStatus, onSelect, isViewed }) => {
  const isOperational = data.status;

  return (
    <Card
      variant="outlined"
      onClick={() => onSelect && onSelect(deviceId)}
      sx={{
        mb: 2,
        borderLeft: 6,
        borderColor: isViewed ? 'primary.main' : (isOperational ? 'success.main' : 'error.main'),
        transition: 'transform 0.2s, box-shadow 0.2s',
        cursor: 'pointer',
        boxShadow: isViewed ? 3 : undefined,
        bgcolor: isViewed ? 'primary.50' : undefined,
        '&:hover': { transform: 'translateX(4px)', bgcolor: isViewed ? 'primary.50' : '#f5f5f5' }
      }}
    >
      <CardContent sx={{ pb: '16px !important' }}>
        <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
          <Typography variant="subtitle1" fontWeight="bold">
            {deviceId}
          </Typography>
          <CircleIcon 
            color={isOperational ? "success" : "error"} 
            sx={{ 
              fontSize: 12, 
              animation: isOperational ? 'pulse 2s infinite' : 'none',
              '@keyframes pulse': {
                '0%': { opacity: 1 },
                '50%': { opacity: 0.5 },
                '100%': { opacity: 1 },
              }
            }} 
          />
        </Box>

        <FormControlLabel
          control={
            <Checkbox
              checked={data.selected || false}
              onChange={(e) => { e.stopPropagation(); onToggleSelect(deviceId, e.target.checked); }}
              size="small"
            />
          }
          label={<Typography variant="body2" color="text.secondary">Select for session</Typography>}
        />
        <FormControlLabel
          control={
            <Checkbox
              checked={data.status || false}
              onChange={(e) => { e.stopPropagation(); onToggleStatus(deviceId, e.target.checked); }}
              size="small"
            />
          }
          label={<Typography variant="body2" color="text.secondary">ON/OFF</Typography>}
        />

        <Box mt={1} display="flex" alignItems="center" gap={2}>
          <Typography variant="caption" color="text.secondary" sx={{ minWidth: 35 }}>
            {data.charge_level}%
          </Typography>
          <Box width="100%">
            <LinearProgress 
              variant="determinate" 
              value={data.charge_level} 
              color={getChargeColor(data.charge_level)}
              sx={{ height: 8, borderRadius: 4 }}
            />
          </Box>
        </Box>
      </CardContent>
    </Card>
  );
};

export default DeviceItem;