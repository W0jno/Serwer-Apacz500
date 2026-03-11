import {
  Box,
  Typography,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  Switch,
  Button,
  Chip,
  LinearProgress,
  Paper,
} from '@mui/material';
import {
  Sensors as SensorsIcon,
  LightbulbOutlined as EmitterIcon,
  Close as CloseIcon,
  ShowChart as SensorReadingIcon,
} from '@mui/icons-material';

const getChargeColor = (level) => {
  if (level <= 20) return 'error';
  if (level <= 50) return 'warning';
  return 'success';
};

const DeviceDetails = ({ deviceId, data, componentStates, onComponentCommand, onClose }) => {
  if (!deviceId || !data) {
    return (
      <Box display="flex" alignItems="center" justifyContent="center" height="100%" color="text.secondary">
        <Typography variant="h6" fontStyle="italic">Click a device to inspect it</Typography>
      </Box>
    );
  }

  const actuators = data.actuators || [];
  const emitters = data.emitters || [];
  const sensors = data.sensors || {};
  const sensorEntries = Object.entries(sensors);
  const states = componentStates || {};

  const handleToggle = (type, name, current) => {
    onComponentCommand(deviceId, type, name, !current);
  };

  return (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      {/* Header */}
      <Box p={2} borderBottom={1} borderColor="divider" display="flex" alignItems="center" justifyContent="space-between">
        <Box>
          <Typography variant="h6" fontWeight="bold">{deviceId}</Typography>
          <Box display="flex" gap={1} mt={0.5}>
            <Chip
              size="small"
              label={data.status ? 'Operational' : 'Offline'}
              color={data.status ? 'success' : 'error'}
            />
            <Chip size="small" label={`${data.charge_level ?? 0}% battery`} variant="outlined" />
          </Box>
        </Box>
        <Button size="small" onClick={onClose} startIcon={<CloseIcon />} color="inherit">
          Close
        </Button>
      </Box>

      {/* Battery bar */}
      <Box px={2} pt={1} pb={0.5}>
        <LinearProgress
          variant="determinate"
          value={data.charge_level ?? 0}
          color={getChargeColor(data.charge_level ?? 0)}
          sx={{ height: 6, borderRadius: 3 }}
        />
      </Box>

      <Box sx={{ flexGrow: 1, overflowY: 'auto', px: 2, pb: 2 }}>
        {/* Actuators */}
        <Box mt={2}>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <SensorsIcon fontSize="small" color="action" />
            <Typography variant="subtitle2" fontWeight="bold" color="text.secondary">
              ACTUATORS ({actuators.length})
            </Typography>
          </Box>
          {actuators.length === 0 ? (
            <Typography variant="body2" color="text.secondary" fontStyle="italic" pl={1}>No actuators</Typography>
          ) : (
            <Paper variant="outlined" sx={{ borderRadius: 2 }}>
              <List dense disablePadding>
                {actuators.map((name, idx) => {
                  const key = `actuator:${name}`;
                  const isActive = states[key] || false;
                  return (
                    <Box key={name}>
                      {idx > 0 && <Divider />}
                      <ListItem sx={{ py: 0.75 }}>
                        <ListItemText
                          primary={<Typography variant="body2">{name}</Typography>}
                          secondary={
                            <Typography variant="caption" color={isActive ? 'primary' : 'text.secondary'}>
                              {isActive ? 'Active' : 'Inactive'}
                            </Typography>
                          }
                        />
                        <ListItemSecondaryAction>
                          <Switch
                            edge="end"
                            size="small"
                            checked={isActive}
                            onChange={() => handleToggle('actuator', name, isActive)}
                          />
                        </ListItemSecondaryAction>
                      </ListItem>
                    </Box>
                  );
                })}
              </List>
            </Paper>
          )}
        </Box>

        {/* Emitters */}
        <Box mt={3}>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <EmitterIcon fontSize="small" color="action" />
            <Typography variant="subtitle2" fontWeight="bold" color="text.secondary">
              EMITTERS ({emitters.length})
            </Typography>
          </Box>
          {emitters.length === 0 ? (
            <Typography variant="body2" color="text.secondary" fontStyle="italic" pl={1}>No emitters</Typography>
          ) : (
            <Paper variant="outlined" sx={{ borderRadius: 2 }}>
              <List dense disablePadding>
                {emitters.map((name, idx) => {
                  const key = `emitter:${name}`;
                  const isOn = states[key] || false;
                  return (
                    <Box key={name}>
                      {idx > 0 && <Divider />}
                      <ListItem sx={{ py: 0.75 }}>
                        <ListItemText
                          primary={<Typography variant="body2">{name}</Typography>}
                          secondary={
                            <Typography variant="caption" color={isOn ? 'warning.dark' : 'text.secondary'}>
                              {isOn ? 'ON' : 'OFF'}
                            </Typography>
                          }
                        />
                        <ListItemSecondaryAction>
                          <Switch
                            edge="end"
                            size="small"
                            checked={isOn}
                            color="warning"
                            onChange={() => handleToggle('emitter', name, isOn)}
                          />
                        </ListItemSecondaryAction>
                      </ListItem>
                    </Box>
                  );
                })}
              </List>
            </Paper>
          )}
        </Box>

        {/* Sensors */}
        <Box mt={3}>
          <Box display="flex" alignItems="center" gap={1} mb={1}>
            <SensorReadingIcon fontSize="small" color="action" />
            <Typography variant="subtitle2" fontWeight="bold" color="text.secondary">
              SENSORS ({sensorEntries.length})
            </Typography>
          </Box>
          {sensorEntries.length === 0 ? (
            <Typography variant="body2" color="text.secondary" fontStyle="italic" pl={1}>No sensor data</Typography>
          ) : (
            <Paper variant="outlined" sx={{ borderRadius: 2 }}>
              <List dense disablePadding>
                {sensorEntries.map(([key, value], idx) => {
                  const isBoolLike = value === 0 || value === 1 || value === true || value === false;
                  const isOn = value === 1 || value === true;
                  return (
                    <Box key={key}>
                      {idx > 0 && <Divider />}
                      <ListItem sx={{ py: 0.75 }}>
                        <ListItemText
                          primary={<Typography variant="body2">{key}</Typography>}
                          secondary={
                            isBoolLike ? (
                              <Typography variant="caption" color={isOn ? 'primary' : 'text.secondary'}>
                                {isOn ? 'ON' : 'OFF'}
                              </Typography>
                            ) : (
                              <Typography variant="caption" color="text.secondary">
                                {String(value)}
                              </Typography>
                            )
                          }
                        />
                        {isBoolLike && (
                          <ListItemSecondaryAction>
                            <Switch
                              edge="end"
                              size="small"
                              checked={isOn}
                              disabled
                              color="primary"
                            />
                          </ListItemSecondaryAction>
                        )}
                      </ListItem>
                    </Box>
                  );
                })}
              </List>
            </Paper>
          )}
        </Box>
      </Box>
    </Box>
  );
};

export default DeviceDetails;
