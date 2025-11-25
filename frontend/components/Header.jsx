import {
  Box,
  AppBar,
  Toolbar,
  Typography,
  Chip,
} from '@mui/material';
import {
  Wifi as WifiIcon,
  WifiOff as WifiOffIcon
} from '@mui/icons-material';

const Header = ({isConnected}) => {
    return (<AppBar position="static" color="default" sx={{ bgcolor: 'white', borderBottom: 1, borderColor: 'divider', boxShadow: 1 }}>
        <Toolbar>
          <Box flexGrow={1}>
            <Typography variant="h6" color="text.primary">
              Device Status Dashboard
            </Typography>
            <Typography variant="caption" color="text.secondary">
              Real-time monitoring via FastAPI & WebSockets
            </Typography>
          </Box>
          <Chip 
            icon={isConnected ? <WifiIcon /> : <WifiOffIcon />} 
            label={isConnected ? "Connected" : "Disconnected"} 
            color={isConnected ? "success" : "error"} 
            variant="filled"
          />
        </Toolbar>
      </AppBar>)
}

export default Header