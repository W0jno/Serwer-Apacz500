import { useMemo, useState } from 'react';
import {
  Box,
  Typography,
  Card,
  CardContent,
  Checkbox,
  FormControlLabel,
  LinearProgress,
  Button,
  Stack,
  MenuItem,
  Select,
  TextField,
} from '@mui/material';
import {
  Circle as CircleIcon,
} from '@mui/icons-material';

const getChargeColor = (level) => {
  if (level <= 20) return 'error';
  if (level <= 50) return 'warning';
  return 'success';
};

const parseInputValue = (text) => {
  const raw = (text ?? '').trim();
  if (raw === '') return '';

  const lower = raw.toLowerCase();
  if (lower === 'true') return true;
  if (lower === 'false') return false;

  const asNumber = Number(raw);
  if (!Number.isNaN(asNumber)) return asNumber;

  return raw;
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
            color={isOperational ? 'success' : 'error'}
            sx={{
              fontSize: 12,
              animation: isOperational ? 'pulse 2s infinite' : 'none',
              '@keyframes pulse': {
                '0%': { opacity: 1 },
                '50%': { opacity: 0.5 },
                '100%': { opacity: 1 },
              },
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

        <Box mt={2} p={1.2} borderRadius={1} bgcolor="#fff" border="1px solid #eee">
          <Typography variant="caption" color="text.secondary" display="block" mb={0.8}>
            Actuator control
          </Typography>

          <Stack direction="row" spacing={1} alignItems="center" mb={1}>
            <Select
              size="small"
              value={activeActuator}
              onChange={(e) => setSelectedActuator(e.target.value)}
              sx={{ minWidth: 120 }}
            >
              {actuators.map((name) => (
                <MenuItem key={name} value={name}>
                  {name}
                </MenuItem>
              ))}
            </Select>
            <Button size="small" variant="outlined" color="success" onClick={() => sendBooleanCommand(true)}>
              ON
            </Button>
            <Button size="small" variant="outlined" color="error" onClick={() => sendBooleanCommand(false)}>
              OFF
            </Button>
          </Stack>

          <Stack direction="row" spacing={1}>
            <TextField
              size="small"
              fullWidth
              placeholder="Custom value (e.g. 0.42 / true / pwm)"
              value={customValue}
              onChange={(e) => setCustomValue(e.target.value)}
            />
            <Button size="small" variant="contained" onClick={sendCustomCommand}>
              Send
            </Button>
          </Stack>
        </Box>
      </CardContent>
    </Card>
  );
};

export default DeviceItem;
