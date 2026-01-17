import * as React from "react";
import { 
    Admin, 
    Resource, 
    List,
    Confirm,
    useRecordContext, 
    Datagrid, 
    TextField,
    SearchInput,
    TopToolbar,
    FunctionField,
    ExportButton,
    useListContext,
    BooleanField,
    BooleanInput,
    useUpdate,
    useNotify,
    Login,
    LoginForm,
    Layout,
    AppBar,
    UserMenu,
    Button as RaButton, // Alias React-Admin's Button to avoid conflict
    useRefresh, // Import useRefresh hook
    useGetList, // Import useGetList to manually trigger a fetch
    useCreate,
    useDataProvider, // Import useDataProvider
    BulkDeleteWithConfirmButton,
    defaultTheme,
    useLogout,
    useLogin,
    downloadCSV,
} from "react-admin";
import jsonExport from 'jsonexport/dist';
import {
    Card,
    CardContent,
    Typography,
    Grid,
    Box,
    Menu,
    MenuItem, 
    ListItemIcon,
    ListItemText,
    Button,
    Divider,
    useTheme,
    Switch,
    FormControlLabel,
    TextField as MuiTextField,
    Paper,
    Link,
    CircularProgress,
    Select, 
    InputLabel,
    Skeleton,
    FormControl,
    Tooltip,
    IconButton,
    InputAdornment,
} from "@mui/material";
import VisibilityIcon from '@mui/icons-material/Visibility';
import VisibilityOffIcon from '@mui/icons-material/VisibilityOff';
import {useCallback, useRef } from "react";
import { createTheme, ThemeProvider } from '@mui/material/styles';
import SchoolIcon from '@mui/icons-material/School';
import AddBusinessIcon from '@mui/icons-material/AddBusiness';
import { useEffect, useState } from "react";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, Legend, ResponsiveContainer } from "recharts";
import LocationOnIcon from '@mui/icons-material/LocationOn';
import WorkIcon from '@mui/icons-material/Work';
import BusinessIcon from '@mui/icons-material/Business';
import PersonIcon from '@mui/icons-material/Person';
import EmailIcon from '@mui/icons-material/Email';
import LanguageIcon from '@mui/icons-material/Language';
import HomeIcon from '@mui/icons-material/Home';
import FilterListIcon from '@mui/icons-material/FilterList';
import PeopleAltIcon from '@mui/icons-material/PeopleAlt';
import CorporateFareIcon from '@mui/icons-material/CorporateFare';
import WorkOutlineIcon from '@mui/icons-material/WorkOutline';
import AssignmentIcon from '@mui/icons-material/Assignment';
import AddIcon from '@mui/icons-material/Add';
import BlockIcon from '@mui/icons-material/Block';
import BadgeIcon from '@mui/icons-material/Badge';
import CategoryIcon from '@mui/icons-material/Category';
import EventIcon from '@mui/icons-material/Event';
import FactoryIcon from '@mui/icons-material/Factory';
import LockIcon from '@mui/icons-material/Lock';
import AdminPanelSettingsIcon from '@mui/icons-material/AdminPanelSettings';
// import RefreshIcon from '@mui/icons-material/Refresh'; // REMOVED: RefreshIcon is no longer needed
import { 
    Dialog, // MUI Dialog
    DialogActions, // MUI DialogActions
    DialogContent, // MUI DialogContent
    DialogContentText, // MUI DialogContentText
    DialogTitle,// MUI DialogTitle
} from "@mui/material";
import './App.css';


const API_BASE_URL = 'http://127.0.0.1:5000/admin';
const API_BASE_URL_AUTH = 'http://127.0.0.1:5000/auth';

// CLEANED Authentication Provider
const authProvider = {
    login: async ({ username, password }) => {
        const request = new Request(`${API_BASE_URL_AUTH}/login`, {
            method: 'POST',
            body: JSON.stringify({ username, password }),
            headers: new Headers({ 
                'Content-Type': 'application/json',
                'X-Requested-With': 'ReactAdmin'
            }),
            credentials: 'include'
        });
        
        try {
            const response = await fetch(request);
            
            // Debug: Log response headers
            /* console.log('Login response headers:', {
                'set-cookie': response.headers.get('set-cookie'),
                'access-control-allow-credentials': response.headers.get('access-control-allow-credentials')
            });
            */
            if (response.status < 200 || response.status >= 300) {
                throw new Error('Invalid credentials');
            }
            return Promise.resolve();
        } catch (error) {
            console.error('Login error:', error);
            return Promise.reject(new Error('Invalid credentials'));
        }
    },
    
    logout: async () => {
        try {
            await fetch(`${API_BASE_URL_AUTH}/logout`, {
                method: 'GET',
                headers: { 'X-Requested-With': 'ReactAdmin' },
                credentials: 'include'
            });
        } catch (error) {
            console.error('Logout error:', error);
        }
        return Promise.resolve();
    },
    
    checkError: ({ status }) => {
        if (status === 401 || status === 403) {
            return Promise.reject();
        }
        return Promise.resolve();
    },
    
    checkAuth: async () => {
        try {
            const response = await fetch(`${API_BASE_URL_AUTH}/api/check-session`, {
                credentials: 'include'
            });
            
            // Debug: Log cookies being sent
            // console.log('CheckAuth cookies:', document.cookie);
            
            if (!response.ok) {
                return Promise.reject();
            }
            return Promise.resolve();
        } catch (error) {
            console.error('CheckAuth error:', error);
            return Promise.reject();
        }
    },
    
    getPermissions: () => Promise.resolve(),
};


// Custom User Menu with proper positioning
const CustomUserMenu = () => (
    <UserMenu 
        sx={{
            '& .MuiPopover-paper': {
                marginTop: '8px',
                transform: 'translateX(-50%) !important',
                left: '50% !important',
                right: 'auto !important',
                minWidth: '120px',
                maxWidth: '200px',
                boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
                borderRadius: '8px'
            }
        }}
    />
);

// Custom AppBar with fixed positioning
const CustomAppBar = () => (
    <AppBar 
        userMenu={<CustomUserMenu />}
        sx={{
            '& .RaAppBar-toolbar': {
                paddingRight: '16px'
            },
            '& .RaAppBar-userMenu': {
                '& .MuiButtonBase-root': {
                    borderRadius: '50%',
                    padding: '8px'
                }
            }
        }}
    />
);

// Custom Layout with fixed AppBar
const CustomLayout = (props) => {
    const logout = useLogout();
    const timer = useRef(null);
    const notify = useNotify();

    const logoutUser = useCallback(() => {
        logout();
        notify('You have been logged out due to inactivity.', { type: 'info' });
    }, [logout, notify]);

    const resetTimer = useCallback(() => {
        if (timer.current) {
            clearTimeout(timer.current);
        }
        // Set timeout to 1 hour (60 minutes * 60 seconds * 1000 milliseconds)
        timer.current = setTimeout(logoutUser, 60 * 60 * 1000);
    }, [logoutUser]);

    useEffect(() => {
        const events = ['mousemove', 'mousedown', 'keypress', 'scroll', 'touchstart'];

        // Set the initial timer
        resetTimer();

        // Add event listeners to reset the timer on user activity
        events.forEach(event => {
            window.addEventListener(event, resetTimer);
        });

        // Cleanup function to remove listeners and timer when the component unmounts
        return () => {
            if (timer.current) {
                clearTimeout(timer.current);
            }
            events.forEach(event => {
                window.removeEventListener(event, resetTimer);
            });
        };
    }, [resetTimer]);

    return <Layout {...props} appBar={CustomAppBar} />;
};

// <<< CREATE A DEDICATED LIGHT THEME FOR THE LOGIN PAGE >>>
const loginPageTheme = createTheme({
  ...defaultTheme,
  palette: {
    ...defaultTheme.palette,
    mode: 'light', // This forces the light mode
  },
});

// Custom Login Page Component
const CustomLoginPage = () => {
    const theme = useTheme();
    const [username, setUsername] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false); // ✅ Add state for password visibility
    const notify = useNotify();
    const login = useLogin();

    const handleSubmit = async (event) => {
        event.preventDefault();
        
        // If fields are empty, just return without any error message
        if (!username || !username.trim() || !password || !password.trim()) {
            return;
        }

        // Proceed with login
        try {
            await login({ username: username.trim(), password });
        } catch (error) {
            notify('Invalid credentials', { type: 'error' });
        }
    };

    return (
        <ThemeProvider theme={loginPageTheme}>
            <Box
                sx={{
                    minHeight: '100vh',
                    background: `linear-gradient(135deg, ${loginPageTheme.palette.primary.main} 0%, ${loginPageTheme.palette.secondary.main} 100%)`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: 2
                }}
            >
                <Paper
                    elevation={10}
                    sx={{
                        padding: 4,
                        borderRadius: 4,
                        maxWidth: 400,
                        width: '100%',
                        backgroundColor: 'rgba(255, 255, 255, 0.95)',
                        backdropFilter: 'blur(10px)'
                    }}
                >
                    <Box sx={{ textAlign: 'center', mb: 3 }}>
                        <AdminPanelSettingsIcon 
                            sx={{ 
                                fontSize: 60, 
                                color: 'primary.main',
                                mb: 2
                            }} 
                        />
                        <Typography variant="h4" sx={{ fontWeight: 700, mb: 1 }}>
                            Admin Portal
                        </Typography>
                        <Typography variant="body2" color="text.secondary">
                            Sign in to access your dashboard
                        </Typography>
                    </Box>
                    
                    <Box component="form" onSubmit={handleSubmit}>
                        <MuiTextField
                            label="Username"
                            name="username"
                            value={username}
                            onChange={(e) => setUsername(e.target.value)}
                            fullWidth
                            required
                            sx={{ 
                                mb: 2,
                                '& .MuiOutlinedInput-root': {
                                    borderRadius: 2,
                                }
                            }}
                        />
                        <MuiTextField
                            label="Password"
                            name="password"
                            type={showPassword ? 'text' : 'password'} // ✅ Toggle between text and password
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            fullWidth
                            required
                            InputProps={{
                                endAdornment: (
                                    <InputAdornment position="end">
                                        <IconButton
                                            onClick={() => setShowPassword(!showPassword)}
                                            edge="end"
                                            aria-label="toggle password visibility"
                                        >
                                            {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                                        </IconButton>
                                    </InputAdornment>
                                )
                            }}
                            sx={{ 
                                mb: 3,
                                '& .MuiOutlinedInput-root': {
                                    borderRadius: 2,
                                }
                            }}
                        />
                        <Button
                            type="submit"
                            variant="contained"
                            fullWidth
                            size="large"
                            sx={{
                                borderRadius: 2,
                                py: 1.5,
                                textTransform: 'none',
                                fontSize: '1rem',
                                fontWeight: 600
                            }}
                        >
                            Sign in
                        </Button>
                    </Box>
                </Paper>
            </Box>
        </ThemeProvider>
    );
};




const customDataProvider = {
    getList: async (resource, params) => {
        try {
            // Extract pagination parameters
            const { page, perPage } = params.pagination;
            const { field, order } = params.sort;
            
            // Build URL with pagination and sorting parameters
            let url = `${API_BASE_URL}/${resource}`;
            const queryParams = new URLSearchParams();
            
            // Add pagination parameters
            queryParams.append('page', page.toString());
            queryParams.append('per_page', perPage.toString());
            
            // Add sorting parameters if available
            if (field && order) {
                queryParams.append('sort', field);
                queryParams.append('order', order.toLowerCase());
            }
            
            // Add filter parameters
            if (params.filter && Object.keys(params.filter).length > 0) {
                Object.entries(params.filter).forEach(([key, value]) => {
                    if (value) {
                        queryParams.append(key, value);
                    }
                });
            }
            
            url += `?${queryParams.toString()}`;
            
            const response = await fetch(url, {
                method: "GET",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                credentials: 'include'
            });

            if (!response.ok) {
                throw new Error(`Failed to fetch ${resource}`);
            }

            const json = await response.json();
            
            // Handle different response formats from your backend
            let data, total;
            
            if (Array.isArray(json)) {
                // If backend returns array directly (current format)
                // Apply client-side pagination as fallback
                const start = (page - 1) * perPage;
                const end = start + perPage;
                data = json.slice(start, end);
                total = json.length;
            } else if (json.data && json.total !== undefined) {
                // If backend returns paginated format
                data = json.data;
                total = json.total;
            } else {
                // Default fallback - ensure we always return an array
                data = json ? (Array.isArray(json) ? json : [json]) : [];
                total = data.length;
            }
            
            // Ensure data is always an array, even when empty
            const safeData = Array.isArray(data) ? data : [];
            const formattedData = safeData.map(item => ({
                id: item.id || item.job_id || item.company_id,
                ...item
            }));

            return { data: formattedData, total: total || 0 };
        } catch (error) {
            console.error("Error fetching data:", error);
            // Always return valid structure, even on error
            return { data: [], total: 0 };
        }
    },

    // ... rest of the methods remain the same
    getOne: async (resource, params) => {
        try {
            const response = await fetch(`${API_BASE_URL}/${resource}/${params.id}`, {
                method: "GET",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                credentials: 'include'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.message || `Failed to fetch ${resource}/${params.id}`);
            }

            const data = await response.json();
            return { data: { ...data, id: params.id } };
        } catch (error) {
            console.error("Error fetching item:", error);
            throw error;
        }
    },

    create: async (resource, params) => {
        try {
            const response = await fetch(`${API_BASE_URL}/${resource}`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: 'include',
                body: JSON.stringify(params.data),
            });

            if (!response.ok) {
                throw new Error(`Failed to create ${resource}`);
            }

            const data = await response.json();
            return { data: { ...data, id: data.id || data.job_id || data.company_id } };
        } catch (error) {
            console.error("Error creating item:", error);
            throw error;
        }
    },

    update: async (resource, params) => {
        try {
            const response = await fetch(`${API_BASE_URL}/${resource}/${params.id}`, {
                method: "PUT",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: 'include',
                body: JSON.stringify(params.data),
            });

            if (!response.ok) {
                throw new Error(`Failed to update ${resource}/${params.id}`);
            }

            const data = await response.json();
            return { data: { ...data, id: params.id } };
        } catch (error) {
            console.error("Error updating item:", error);
            throw error;
        }
    },

    delete: async (resource, params) => {
        try {
            const response = await fetch(`${API_BASE_URL}/${resource}/${params.id}`, {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: 'include',
                body: JSON.stringify(params.data),
            });

            if (!response.ok) {
                throw new Error(`Failed to delete ${resource}/${params.id}`);
            }

            return { data: { id: params.id } };
        } catch (error) {
            console.error("Error deleting item:", error);
            throw error;
        }
    },
    
    deleteMany: async (resource, params) => {
        try {
            const response = await fetch(`${API_BASE_URL}/${resource}/bulk`, {
                method: "DELETE",
                headers: {
                    "Content-Type": "application/json",
                },
                credentials: 'include',
                body: JSON.stringify({ ids: params.ids }),
            });

            if (!response.ok) {
                throw new Error(`Failed to delete ${resource} items`);
            }

            return { data: params.ids };
        } catch (error) {
            console.error("Delete many error:", error);
            throw error;
        }
    },
};

const UserBulkActionButtons = () => (
    <BulkDeleteWithConfirmButton
        confirmTitle="Delete Job Seekers"
        confirmContent="Are you sure you want to delete the selected job seekers? This action cannot be undone."
    />
);

const CompanyBulkActionButtons = () => (
    <BulkDeleteWithConfirmButton
        confirmTitle="Delete Companies"
        confirmContent="Are you sure you want to delete the selected companies? This action cannot be undone."
    />
);

const JobBulkActionButtons = () => (
    <BulkDeleteWithConfirmButton
        confirmTitle="Delete Jobs"
        confirmContent="Are you sure you want to delete the selected jobs? This action cannot be undone."
    />
);

const metricIcons = {
    job_seekers: <PeopleAltIcon sx={{ fontSize: 40, color: 'white' }} />,
    companies: <CorporateFareIcon sx={{ fontSize: 40, color: 'white' }} />,
    jobs: <WorkOutlineIcon sx={{ fontSize: 40, color: 'white' }} />,
    applications: <AssignmentIcon sx={{ fontSize: 40, color: 'white' }} />
};
// Replace your existing Dashboard component with this updated version

const Dashboard = () => {
    const theme = useTheme();
    const [metrics, setMetrics] = useState({
        job_seekers: 0,
        companies: 0,
        jobs: 0,
        applications: 0,
    });
    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [range, setRange] = useState('weekly'); // 'weekly' | 'monthly' | 'yearly' | 'ten_years'

    const fetchDashboardData = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);

            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // changed from 5 to 10s timeout

            const response = await fetch(
                `${API_BASE_URL}/dashboard?range=${range}`,
                {
                    method: 'GET',
                    headers: {
                        'Content-Type': 'application/json',
                        Accept: 'application/json',
                    },
                    credentials: 'include',
                    signal: controller.signal,
                }
            );

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();

            const transformedMetrics = {
                job_seekers: data.metrics?.users || data.metrics?.job_seekers || 0,
                companies: data.metrics?.companies || 0,
                jobs: data.metrics?.jobs || 0,
                applications: data.metrics?.applications || 0,
            };

            setMetrics(transformedMetrics);
            setChartData(
                data.trends?.map((item) => ({
                    x: item.x, // backend: day name / Week N / month abbr / year
                    tooltip_label: item.tooltip_label,
                    applications: item.applications,
                    registrations: item.logins,
                })) || []
            );
        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            setError(error.message);

            setMetrics({
                job_seekers: 0,
                companies: 0,
                jobs: 0,
                applications: 0,
            });
            setChartData([]);
        } finally {
            setLoading(false);
        }
    }, [range]);

    useEffect(() => {
        // Fetch on mount and whenever range changes
        fetchDashboardData();

        // Auto-refresh every 30 seconds with current range
        const intervalId = setInterval(fetchDashboardData, 30000);
        return () => clearInterval(intervalId);
    }, [fetchDashboardData]);

    const metricColors = [
        theme.palette.primary.main,
        theme.palette.secondary.main,
        '#4caf50',
        '#9c27b0',
    ];

    const formatMetricName = (key) => {
        return key === 'job_seekers'
            ? 'JOB SEEKERS'
            : key.replace('_', ' ').toUpperCase();
    };

    // Initial loading state
    if (loading && Object.values(metrics).every((val) => val === 0)) {
        return (
            <Box
                p={3}
                display="flex"
                justifyContent="center"
                alignItems="center"
                minHeight="200px"
            >
                <Box textAlign="center">
                    <CircularProgress size={40} />
                    <Typography variant="body1" sx={{ mt: 1 }}>
                        Loading...
                    </Typography>
                </Box>
            </Box>
        );
    }

    // Initial error state
    if (error && Object.values(metrics).every((val) => val === 0)) {
        return (
            <Box
                p={3}
                display="flex"
                justifyContent="center"
                alignItems="center"
                minHeight="400px"
            >
                <Box textAlign="center">
                    <Typography variant="h6" color="error" sx={{ mb: 2 }}>
                        Failed to load dashboard data
                    </Typography>
                    <Typography
                        variant="body2"
                        color="text.secondary"
                        sx={{ mb: 3 }}
                    >
                        {error}
                    </Typography>
                </Box>
            </Box>
        );
    }

    return (
        <Box p={3}>
            {/* Small refresh indicator while background updates run */}
            {loading && (
                <Box sx={{ display: 'flex', justifyContent: 'center', mb: 2 }}>
                    <CircularProgress size={20} />
                    <Typography variant="body2" sx={{ ml: 1 }}>
                        Refreshing...
                    </Typography>
                </Box>
            )}

            {/* Metric cards (unchanged design) */}
            <Grid container spacing={3}>
                {Object.entries(metrics).map(([key, value], index) => (
                    <Grid item xs={12} sm={6} md={6} lg={3} key={key}>
                        <Card
                            elevation={3}
                            sx={{
                                background: metricColors[index],
                                color: 'white',
                                borderRadius: 3,
                                overflow: 'visible',
                                '&:hover': {
                                    transform: 'translateY(-4px)',
                                    transition: 'transform 0.3s',
                                },
                            }}
                        >
                            <CardContent>
                                <Box
                                    display="flex"
                                    justifyContent="space-between"
                                    alignItems="center"
                                >
                                    <div>
                                        <Typography
                                            variant="subtitle2"
                                            sx={{
                                                opacity: 0.9,
                                                letterSpacing: 1,
                                            }}
                                        >
                                            {formatMetricName(key)}
                                        </Typography>
                                        <Typography
                                            variant="h3"
                                            sx={{ fontWeight: 700, mt: 1 }}
                                        >
                                            {value}
                                        </Typography>
                                    </div>
                                    <Box
                                        sx={{
                                            bgcolor: 'rgba(255,255,255,0.2)',
                                            p: 1.5,
                                            borderRadius: 3,
                                        }}
                                    >
                                        {metricIcons[key]}
                                    </Box>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>

            <Divider sx={{ my: 4, bgcolor: 'divider', height: 2 }} />

            {/* Chart card – slightly taller, no explicit Refresh button */}
            <Box
                sx={{
                    height: 460,
                    bgcolor: 'background.paper',
                    borderRadius: 3,
                    p: 3,
                    boxShadow: 1,
                }}
            >
                <Box
                    sx={{
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        mb: 3,
                    }}
                >
                    <Typography variant="h6" sx={{ color: 'text.primary' }}>
                        Application and Registration Activity Trends
                    </Typography>

                    <FormControl size="small" sx={{ minWidth: 120, maxWidth: 240 }}>
                        <InputLabel id="range-label">Range</InputLabel>
                        <Select
                            labelId="range-label"
                            value={range}
                            label="Range"
                            onChange={(e) => setRange(e.target.value)}
                        >
                            <MenuItem value="weekly">This Week</MenuItem>
                            <MenuItem value="monthly">This Month</MenuItem>
                            <MenuItem value="six_months">Last 6 Months</MenuItem>
                            <MenuItem value="yearly">This Year</MenuItem>
                            <MenuItem value="ten_years">Last 10 Years</MenuItem>
                        </Select>
                    </FormControl>
                </Box>

                <ResponsiveContainer width="100%" height="88%">
                    <LineChart 
                        data={chartData} 
                        margin={{ top: 10, right: 30, left: 20, bottom: 40 }}
                    >
                        <CartesianGrid strokeDasharray="3 3" stroke={theme.palette.divider} />
                        <XAxis 
                            dataKey="x" 
                            tickMargin={15} 
                            label={{ value: 'Time Period', position: 'bottom', offset: 30, fill: theme.palette.text.secondary }}
                            tick={{ fill: theme.palette.text.secondary, fontSize: 15, angle: 0, textAnchor: 'middle' }}
                        />
                        <YAxis 
                            allowDecimals={false}
                            label={{ value: 'Activity Counts', angle: -90, position: 'insideLeft', style: { textAnchor: 'middle' }, offset: 10, fill: theme.palette.text.secondary }}
                            tick={{ fill: theme.palette.text.secondary, fontSize: 15 }}
                        />
                        <RechartsTooltip 
                            labelFormatter={(value, payload) => {
                                if (payload && payload.length > 0 && payload[0].payload.tooltip_label) {
                                    return payload[0].payload.tooltip_label;
                                }
                                return value;
                            }}
                            contentStyle={{
                                backgroundColor: theme.palette.background.paper,
                                color: theme.palette.text.primary,
                                borderRadius: '8px',
                                borderColor: theme.palette.divider,
                                boxShadow: theme.shadows[3],
                            }}
                            cursor={{ stroke: theme.palette.action.hover, strokeWidth: 2 }}
                        />
                        <Legend 
                            wrapperStyle={{ paddingTop: '60px' }}
                            iconSize={16}
                            iconType="circle"
                        />
                        <Line 
                            type="monotone" 
                            dataKey="applications" 
                            name="Applications" 
                            stroke={theme.palette.primary.main} 
                            strokeWidth={2}
                            activeDot={{ r: 6 }}
                            dot={{ r: 3 }}
                        />
                        <Line 
                            type="monotone" 
                            dataKey="registrations" 
                            name="Registrations" 
                            stroke="#388e3c" 
                            strokeWidth={2}
                            activeDot={{ r: 6 }}
                            dot={{ r: 3 }}
                        />
                    </LineChart>
                </ResponsiveContainer>
            </Box>
        </Box>
    );
};




// This component displays details in a popup.
// Fixed DetailsDialog component with better alignment
const DetailsDialog = ({ open, onClose, onExited, title, data, loading, fieldsOrder }) => {
    // Helper to format keys (e.g., 'company_name' -> 'Company Name')
    const formatLabel = (key) => {
        if (key === 'is_banned') return 'Ban Status';
        return key
            .split('_')
            .map(word => word.charAt(0).toUpperCase() + word.slice(1))
            .join(' ');
    };

    // Helper to format values
    const formatValue = (key, value) => {
        // Show em dash for null, undefined, or empty string
        if (value === null || value === undefined || value === '') {
            return '—';
        }
        
        if (typeof value === 'boolean') {
            return value ? 'Yes' : 'No';
        }

        // Special formatting for created_at if it's a date string
        if (key === 'created_at' && typeof value === 'string' && !isNaN(new Date(value))) {
            return `${new Date(value).toLocaleDateString()} ${new Date(value).toLocaleTimeString()}`;
        }

        return String(value);
    };

    const displayData = {};
    if (data && fieldsOrder) {
        fieldsOrder.forEach(key => {
            if (data.hasOwnProperty(key)) {
                displayData[key] = data[key];
            }
        });
    } else if (data) {
        // Fallback if no fieldsOrder is provided, but still filter out some
        Object.entries(data).forEach(([key, value]) => {
            if (key === 'id' || key === 'login_id' || key.endsWith('_picture') || key === 'logo' || key === 'description' || key === 'about_me') {
                return; // Skip non-display fields and specific removals
            }
            displayData[key] = value;
        });
    }

    return (
        <Dialog open={open} onClose={onClose} TransitionProps={ { onExited: onExited }} fullWidth maxWidth="sm" scroll="paper">
            <DialogTitle>{title}</DialogTitle>
            <DialogContent dividers>
                {loading && (
                    <Box sx={{ display: 'flex', justifyContent: 'center', p: 4 }}>
                        <CircularProgress />
                    </Box>
                )}
                {!loading && data && (
                    <Box sx={{ mt: 1 }}>
                        {Object.entries(displayData).map(([key, value]) => (
                            <Box 
                                key={key} 
                                sx={{ 
                                    display: 'flex',
                                    flexDirection: { xs: 'column', sm: 'row' },
                                    mb: 2,
                                    minHeight: 'auto'
                                }}
                            >
                                <Box sx={{ 
                                    minWidth: { xs: 'auto', sm: 120 },
                                    maxWidth: { xs: 'none', sm: 120 },
                                    mr: { xs: 0, sm: 2 },
                                    mb: { xs: 0.5, sm: 0 },
                                    flexShrink: 0
                                }}>
                                    <Typography 
                                        variant="subtitle2" 
                                        color="text.secondary" 
                                        fontWeight="bold"
                                        sx={{ 
                                            fontSize: '0.875rem',
                                            lineHeight: 1.2
                                        }}
                                    >
                                        {formatLabel(key)}
                                    </Typography>
                                </Box>
                                <Box sx={{ flex: 1, minWidth: 0 }}>
                                    <Typography 
                                        variant="body2" 
                                        sx={{ 
                                            wordBreak: 'break-word',
                                            fontSize: '0.875rem',
                                            lineHeight: 1.4
                                        }}
                                    >
                                        {formatValue(key, value)}
                                    </Typography>
                                </Box>
                            </Box>
                        ))}
                    </Box>
                )}
                {!loading && !data && (
                    <Typography variant="body1" sx={{ p: 4, textAlign: 'center' }}>
                        No details available.
                    </Typography>
                )}
            </DialogContent>
            <DialogActions>
                <Button onClick={onClose}>Close</Button>
            </DialogActions>
        </Dialog>
    );
};

// ClickableNameField Component with Truncation
const ClickableNameField = ({ source, resource, maxChars = 25 }) => {
    const record = useRecordContext();
    const dataProvider = useDataProvider();
    const [open, setOpen] = useState(false);
    const [details, setDetails] = useState(null);
    const [loading, setLoading] = useState(false);
    const notify = useNotify();

    if (!record) return null;

    const value = record[source];
    
    // Show em dash for null, undefined, or empty string
    if (value === undefined || value === null || value === '') {
        return <span style={{ color: '#999' }}>—</span>;
    }

    const text = String(value);
    const isLong = text.length > maxChars;
    const display = isLong ? text.slice(0, maxChars).trimEnd() + '...' : text;

    const handleClick = (event) => {
        event.stopPropagation();
        event.preventDefault();
        setOpen(true);
        setLoading(true);

        dataProvider
            .getOne(resource, { id: record.id })
            .then(({ data }) => {
                setDetails(data);
                setLoading(false);
            })
            .catch((error) => {
                setLoading(false);
                setOpen(false);
                notify(`Error fetching details: ${error.message}`, { type: 'error' });
            });
    };

    const handleClose = () => {
        setOpen(false);
        // Don't clear details immediately - let the modal animation finish first
        // Details will be overwritten when opening a new modal anyway
    };

    // Clear details after modal is fully closed (after animation)
    const handleExited = () => {
        setDetails(null);
        setLoading(false);
    };

    const dialogTitle =
        resource === 'users'
            ? `${record.name} - Job Seeker Details`
            : `${record.company_name} - Company Details`;

    let fieldsOrder;
    if (resource === 'users') {
        fieldsOrder = ['age', 'email', 'phone', 'college_name', 'about_me', 'is_banned', 'created_at'];
    } else if (resource === 'companies') {
        fieldsOrder = ['email', 'address', 'industry', 'description', 'website', 'is_banned', 'created_at'];
    }

    const content = (
        <span
            style={{
                display: 'inline-block',
                maxWidth: '100%',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
            }}
        >
            {display}
        </span>
    );

    return (
        <>
            <Tooltip title={text}>
                <Link
                    component="button"
                    variant="body2"
                    onClick={handleClick}
                    sx={{
                        textAlign: 'left',
                        textTransform: 'none',
                        textDecoration: 'none',
                        color: 'primary.main',
                        cursor: 'pointer',
                        '&:hover': { textDecoration: 'underline' },
                        display: 'inline-block',
                        maxWidth: '100%',
                    }}
                >
                    {content}
                </Link>
            </Tooltip>
            <DetailsDialog
                open={open}
                onClose={handleClose}
                onExited={handleExited}
                title={dialogTitle}
                data={details}
                loading={loading}
                fieldsOrder={fieldsOrder}
            />
        </>
    );
};

const FilterDropdown = () => {
    const { resource, filterValues, setFilters } = useListContext();
    const [anchorEl, setAnchorEl] = useState(null);
    const open = Boolean(anchorEl);
    const theme = useTheme();
    
    const handleClick = (event) => setAnchorEl(event.currentTarget);
    const handleClose = () => setAnchorEl(null);
    
    const applyFilter = (filter) => {
        setFilters({ ...filterValues, q: filter });
        handleClose();
    };
    
    const getFilterOptions = () => {
        switch(resource) {
            case 'users':
                return [
                    { label: "Name", value: "name:", icon: <PersonIcon /> },
                    { label: "Email", value: "email:", icon: <EmailIcon /> },
                    { label: "College", value: "college:", icon: <SchoolIcon /> }, // Changed to "college:" - adjust based on your actual field
                ];
            case 'companies':
                return [
                    { label: "Company Name", value: "company_name:", icon: <BusinessIcon /> },
                    { label: "Email", value: "email:", icon: <EmailIcon /> },
                    { label: "Industry", value: "industry:", icon: <FactoryIcon /> }
                ];
            case 'jobs':
                return [
                    { label: "Title", value: "title:", icon: <WorkIcon /> },
                    { label: "Company", value: "company:", icon: <FactoryIcon /> },
                    { label: "Job Type", value: "job_type:", icon: <CategoryIcon /> },
                    { label: "Status", value: "status:", icon: <LockIcon /> }
                ];
            default:
                return [];
        }
    };

    const filterOptions = getFilterOptions();
    
    return filterOptions.length > 0 && (
        <>
            <Button
                startIcon={<FilterListIcon />}
                onClick={handleClick}
                variant="contained"
                size="medium"
                sx={{ 
                    mr: 2,
                    borderRadius: 20,
                    textTransform: 'none',
                    px: 3,
                    bgcolor: theme.palette.background.paper,
                    color: theme.palette.text.primary,
                    '&:hover': {
                        bgcolor: theme.palette.action.hover
                    }
                }}
            >
                Filter By
            </Button>
            <Menu
                anchorEl={anchorEl}
                open={open}
                onClose={handleClose}
                PaperProps={{ 
                    sx: { 
                        borderRadius: 3,
                        mt: 1,
                        boxShadow: 3
                    } 
                }}
            >
                {filterOptions.map((option) => (
                    <MenuItem 
                        key={option.value} 
                        onClick={() => applyFilter(option.value)}
                        sx={{ py: 1.5, minWidth: 200 }}
                    >
                        <ListItemIcon sx={{ minWidth: 40 }}>
                            {React.cloneElement(option.icon, { 
                                sx: { color: theme.palette.text.secondary } 
                            })}
                        </ListItemIcon>
                        <ListItemText 
                            primary={option.label} 
                            primaryTypographyProps={{ variant: 'body2' }}
                        />
                    </MenuItem>
                ))}
            </Menu>
        </>
    );
};

const industryOptions = [
  "Agriculture, Forestry, and Fishing",
  "Mining and Quarrying",
  "Manufacturing",
  "Electricity, Gas, Steam, and Air Conditioning Supply",
  "Water Supply; Sewerage, Waste Management, and Remediation Activities",
  "Construction",
  "Wholesale and Retail Trade; Repair of Motor Vehicles and Motorcycles",
  "Transportation and Storage",
  "Accommodation and Food Service Activities",
  "Information and Communication",
  "Financial and Insurance Activities",
  "Real Estate Activities",
  "Professional, Scientific, and Technical Activities",
  "Administrative and Support Service Activities",
  "Public Administration and Defence; Compulsory Social Security",
  "Education",
  "Human Health and Social Work Activities",
  "Arts, Entertainment, and Recreation",
  "Other Service Activities",
  "Activities of Households as Employers",
  "Activities of Extraterritorial Organizations and Bodies"
];

// --- Shared safety helpers like profile form ---

const containsScript = (value = '') =>
    /<\s*script[\s\S]*?>[\s\S]*?<\s*\/\s*script\s*>/i.test(value);

const containsDangerousProtocols = (value = '') =>
    /(javascript\s*:|data\s*:)/i.test(value);

const isDangerousUrl = (url = '') =>
    /^(javascript:|data:)/i.test(url);

const hasMultipleUrls = (url = '') =>
    /\s/.test(url);

const isHttpUrl = (url = '') =>
    /^https?:\/\//i.test(url);

const isValidURL = (url = '') => {
    try {
        new URL(url);
        return true;
    } catch {
        return false;
    }
};

const createExporter = (resourceName) => (data) => {
    // console.log('Exporting:', resourceName, 'Records:', data?.length || 0);
    
    // If no data, export empty file
    if (!data || data.length === 0) {
        // console.warn('No data to export for', resourceName);
        jsonExport([], (err, csv) => {
            downloadCSV(csv || '', getFilename(resourceName));
        });
        return;
    }

    // Map resource names to proper filename
    const getFilename = (resource) => {
        switch(resource) {
            case 'users':
                return 'jobseekers';
            case 'companies':
                return 'companies';
            case 'jobs':
                return 'jobs';
            default:
                return resource;
        }
    };

    // Define field mapping based on resource
    const getFieldsForResource = (resource, sampleRecord) => {
        // console.log('Sample record keys:', Object.keys(sampleRecord));

        switch(resource) {
            case 'users':
                return {
                    'S.No': (record, index) => index + 1,
                    'Name': 'name',
                    'Email': 'email',
                    'College': 'college_name',
                    'Banned': 'is_banned'
                };
            case 'companies':
                return {
                    'S.No': (record, index) => index + 1,
                    'Company Name': 'company_name',
                    'Email': 'email',
                    'Industry': 'industry',
                    'Banned': 'is_banned'
                };
            case 'jobs':
                return {
                    'S.No': (record, index) => index + 1,
                    'Job Title': 'title',
                    'Company': 'company_name',
                    'Job Type': 'job_type',
                    'Location': 'location',
                    'Salary': 'salary',
                    'Total Vacancy': 'total_vacancy',
                    'Filled Vacancy': 'filled_vacancy',
                    'Status': 'status'
                };
            default:
                return {};
        }
    };

    const fieldMapping = getFieldsForResource(resourceName, data[0]);
    
    const dataForExport = data.map((record, index) => {
        const exportRecord = {};
        
        Object.entries(fieldMapping).forEach(([exportFieldName, sourceField]) => {
            if (typeof sourceField === 'function') {
                // For computed fields like S.No
                exportRecord[exportFieldName] = sourceField(record, index);
            } else {
                // For regular fields
                exportRecord[exportFieldName] = record[sourceField];
            }
        });
        
        return exportRecord;
    });

    // console.log('Export data formatted:', dataForExport.slice(0, 2)); // Log first 2 records

    jsonExport(dataForExport, (err, csv) => {
        if (err) {
            console.error('Export error:', err);
            return;
        }
        downloadCSV(csv, getFilename(resourceName));
        // console.log('Export successful:', getFilename(resourceName) + '.csv');
    });
};

const AddCompanyDialog = ({ open, handleClose }) => {
    const [create] = useCreate();
    const notify = useNotify();
    const refresh = useRefresh();
    const dataProvider = useDataProvider();
    const theme = useTheme();

    const [formData, setFormData] = useState({ company_name: '', email: '', address: '', website: '', logo: '', description: '', industry: '', password: '' });
    const [passwordError, setPasswordError] = useState('');
    const [emailError, setEmailError] = useState('');
    const [companyNameError, setCompanyNameError] = useState('');
    const [isCheckingCompany, setIsCheckingCompany] = useState(false);
    const [showPassword, setShowPassword] = useState(false);

    const [isVerifyingWebsite, setIsVerifyingWebsite] = useState(false);
    const [isVerifyingLogo, setIsVerifyingLogo] = useState(false);

    const handleChange = (e) => {
        const { name, value } = e.target;
        setFormData({ ...formData, [name]: value });
        if (name === 'password') setPasswordError('');
        if (name === 'email') setEmailError('');
        if (name === 'company_name') setCompanyNameError('');
    };

    const validatePassword = (password) => {
        if (password.includes(' ')) return 'Password cannot contain spaces.';
        if (!/^[a-zA-Z0-9@#$%^&+=]+$/.test(password)) return 'Password can only contain letters, numbers, and @#$%^&+=';
        if (password.length < 8) return 'Password must be at least 8 characters long.';
        return '';
    };

    const validateEmail = (email) => {
        if (!email) return 'Email address is required.';
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Please enter a valid email address.';
        return '';
    };

    const validateCompanyName = (companyName) => {
        if (!companyName) return 'Company Name is required.';
        return '';
    };

    const checkCompanyNameExists = async (companyName) => {
        try {
            const { data } = await dataProvider.getList('companies', {
                pagination: { page: 1, perPage: 1000 },
                sort: { field: 'id', order: 'ASC' },
                filter: {},
            });
            return data.some(
                (company) =>
                    (company.company_name || '').toLowerCase() === companyName.toLowerCase()
            );
        } catch (error) {
            console.error('Error checking company name:', error);
            return false; // don't block creation if check fails
        }
    };
    
    const resetForm = () => {
        setFormData({ company_name: '', email: '', address: '', website: '', logo: '', description: '', industry: '', password: '' });
        setPasswordError('');
        setEmailError('');
        setCompanyNameError('');
    };
    
    const handleDialogClose = () => {
        resetForm();
        handleClose();
    };

    const handleSubmit = async () => {
        const passwordValidationMessage = validatePassword(formData.password);
        const emailValidationMessage = validateEmail(formData.email);
        const companyNameValidationMessage = validateCompanyName(formData.company_name);

        if (passwordValidationMessage) setPasswordError(passwordValidationMessage);
        if (emailValidationMessage) setEmailError(emailValidationMessage);
        if (companyNameValidationMessage) setCompanyNameError(companyNameValidationMessage);

        if (passwordValidationMessage || emailValidationMessage || companyNameValidationMessage) {
            return;
        }

        // === extra script / URL checks you already added go here ===

        setIsCheckingCompany(true);
        try {
            const companyExists = await checkCompanyNameExists(formData.company_name);
            if (companyExists) {
                setCompanyNameError('A company with this name already exists.');
                setIsCheckingCompany(false);
                return;
            }
        } catch (error) {
            setIsCheckingCompany(false);
            notify(error.message || 'Unable to verify company name. Please try again.', { type: 'error' });
            return;
        }

        //setIsCheckingCompany(false);

        if (formData.website) setIsVerifyingWebsite(true);
        if (formData.logo) setIsVerifyingLogo(true);

        try {
            const response = await fetch(`${API_BASE_URL}/companies`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                credentials: 'include',
                body: JSON.stringify({
                    ...formData,
                    // Backend expects snake_case:
                    is_banned: false,
                }),
            });

            const json = await response.json().catch(() => ({}));

            if (!response.ok) {
                // This path runs for all validation failures and server errors
                const msg =
                    json.message ||
                    json.error ||
                    'Failed to add company. Please check the form and try again.';
                notify(msg, { type: 'error' });
                return;
            }

            // Only reached on actual 2xx/201 success
            notify(json.message || 'Company added successfully!', { type: 'success' });
            refresh();
            handleDialogClose();
        } catch (error) {
            notify(
                error?.message || 'Network error while adding company. Please try again.',
                { type: 'error' }
            );
        } finally {
            setIsCheckingCompany(false);
            setIsVerifyingWebsite(false);
            setIsVerifyingLogo(false);
        }
    };

    return (
        <Dialog open={open} onClose={handleDialogClose} fullWidth maxWidth="md">
            <Box sx={{
                p: 3,
                bgcolor: 'primary.main',
                color: 'primary.contrastText',
                display: 'flex',
                alignItems: 'center',
                gap: 2
            }}>
                <AddBusinessIcon sx={{ fontSize: 40 }}/>
                <Box>
                    <Typography variant="h5" component="h2" sx={{ fontWeight: 'bold' }}>
                        Create New Company
                    </Typography>
                    <Typography variant="body2" sx={{ opacity: 0.8 }}>
                        Fill out the form to register a new company profile.
                    </Typography>
                </Box>
            </Box>
            
            <DialogContent sx={{ p: 3 }}>
                {/* PRIMARY DETAILS SECTION */}
                <Box sx={{ mb: 4 }}>
                    <Typography variant="subtitle2" gutterBottom sx={{ color: 'text.secondary', fontWeight: 600, mb: 1 }}>
                        PRIMARY DETAILS
                    </Typography>
                    <Divider sx={{ mb: 3 }} />
                    
                    <Box sx={{
                        display: 'grid',
                        gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
                        gap: 3,
                        mb: 3
                    }}>
                        <MuiTextField 
                            autoFocus 
                            name="company_name" 
                            label="Company Name" 
                            fullWidth 
                            variant="outlined" 
                            value={formData.company_name} 
                            onChange={handleChange} 
                            required 
                            error={!!companyNameError} 
                            helperText={companyNameError} 
                        />
                        <MuiTextField 
                            name="email" 
                            label="Email Address" 
                            type="email" 
                            fullWidth 
                            variant="outlined" 
                            value={formData.email} 
                            onChange={handleChange} 
                            required 
                            error={!!emailError} 
                            helperText={emailError}
                            autoComplete="new-email"
                        />
                    </Box>
                    
                    <Box sx={{
                        display: 'grid',
                        gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
                        gap: 3
                    }}>
                        <MuiTextField
                            name="password"
                            label="Password"
                            type={showPassword ? "text" : "password"}  // Toggle between text and password
                            fullWidth
                            variant="outlined"
                            value={formData.password}
                            onChange={handleChange}
                            required
                            error={!!passwordError}
                            helperText={passwordError || "8+ characters, letters, numbers, and special characters"}
                            InputProps={{
                                endAdornment: (
                                <InputAdornment position="end">
                                    <IconButton
                                    onClick={() => setShowPassword(!showPassword)}
                                    onMouseDown={(e) => e.preventDefault()}
                                    edge="end"
                                    aria-label="toggle password visibility"
                                    >
                                    {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                                    </IconButton>
                                </InputAdornment>
                                ),
                            }}
                        />

                        <FormControl fullWidth variant="outlined">
                            <InputLabel id="industry-label">Industry</InputLabel>
                            <Select 
                                labelId="industry-label" 
                                id="industry" 
                                name="industry" 
                                value={formData.industry} 
                                onChange={handleChange} 
                                label="Industry"
                            >
                                <MenuItem value=""><em>None</em></MenuItem>
                                {industryOptions.map((option) => (
                                    <MenuItem key={option} value={option}>{option}</MenuItem>
                                ))}
                            </Select>
                        </FormControl>
                    </Box>
                </Box>

                {/* ADDITIONAL INFORMATION SECTION */}
                <Box>
                    <Typography variant="subtitle2" gutterBottom sx={{ color: 'text.secondary', fontWeight: 600, mb: 1 }}>
                        ADDITIONAL INFORMATION
                    </Typography>
                    <Divider sx={{ mb: 3 }} />
                    
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                        <MuiTextField 
                            name="address" 
                            label="Address" 
                            fullWidth 
                            multiline 
                            rows={2} 
                            variant="outlined" 
                            value={formData.address} 
                            onChange={handleChange} 
                        />
                        
                        <Box sx={{
                            display: 'grid',
                            gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' },
                            gap: 3
                        }}>
                            <MuiTextField 
                                name="website" 
                                label="Website URL" 
                                type="url" 
                                fullWidth 
                                variant="outlined" 
                                value={formData.website} 
                                onChange={handleChange} 
                            />
                            <MuiTextField 
                                name="logo" 
                                label="Logo URL" 
                                type="url" 
                                fullWidth 
                                variant="outlined" 
                                value={formData.logo} 
                                onChange={handleChange} 
                            />
                        </Box>
                        
                        <MuiTextField 
                            name="description" 
                            label="Company Description" 
                            fullWidth 
                            multiline 
                            rows={3} 
                            variant="outlined" 
                            value={formData.description} 
                            onChange={handleChange} 
                        />
                    </Box>
                </Box>
            </DialogContent>
            
            <DialogActions sx={{ p: 3, borderTop: `1px solid ${theme.palette.divider}`, gap: 2 }}>
                <Button onClick={handleDialogClose} size="large">Cancel</Button>
                <Button 
                    onClick={handleSubmit} 
                    variant="contained" 
                    size="large"
                    disabled={isCheckingCompany} 
                    startIcon={isCheckingCompany ? <CircularProgress size={20} color="inherit" /> : <AddIcon />}
                >
                    {isCheckingCompany ? 'Checking...' : 'Add Company'}
                </Button>
            </DialogActions>
        </Dialog>
    );
};
const AddCompanyButton = () => {
  const theme = useTheme();
  const [open, setOpen] = useState(false);

  const handleClickOpen = () => {
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
  };

  return (
    <>
      <Button
        startIcon={<AddIcon />}
        onClick={handleClickOpen}
        variant="contained"
        color="primary"
        size="medium"
        sx={{
          ml: 2,
          borderRadius: 20,
          textTransform: 'none',
          px: 3
        }}
      >
        Add Company
      </Button>
      <AddCompanyDialog open={open} handleClose={handleClose} />
    </>
  );
};


const ListActions = (props) => {
    const { resource } = useListContext();
    
    return (
        <TopToolbar {...props} sx={{ p: 2, bgcolor: 'background.default' }}>
            <FilterDropdown />
            <ExportButton 
                exporter={createExporter(resource)}
                sx={{ 
                    borderRadius: 20,
                    textTransform: 'none',
                    px: 3,
                    '&:hover': { bgcolor: 'action.hover' }
                }}
            />
            {resource === 'companies' && <AddCompanyButton />}
        </TopToolbar>
    );
};

const StyledDatagrid = ({ children, ...props }) => {
    const { data, isLoading, error } = useListContext();

    return (
        <>
            <Datagrid
                {...props}
                sx={{
                    '& .RaDatagrid-table': {
                        tableLayout: 'fixed',
                        width: '100%',
                    },

                    // Truncate ONLY non-checkbox columns (skip first cell)
                    '& .RaDatagrid-headerCell:not(:first-of-type), & .RaDatagrid-rowCell:not(:first-of-type)': {
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap',
                    },

                    // Ensure the selection checkbox column has enough width
                    '& .MuiTableCell-paddingCheckbox': {
                        width: '64px !important',
                        minWidth: '64px !important',
                        maxWidth: '64px !important',
                        overflow: 'visible !important',
                    },

                    '& .RaDatagrid-headerCell': {
                        bgcolor: 'background.default',
                        fontWeight: 700,
                    },
                    '& .RaDatagrid-rowCell': {
                        py: 2,
                    },
                    '& .RaDatagrid-row:hover': {
                        bgcolor: 'action.hover',
                    },
                }}
                rowClick="edit"
            >
                {children}
            </Datagrid>

            {!isLoading && !error && (!data || data.length === 0) && (
                <Box sx={{ 
                    display: 'flex', 
                    flexDirection: 'column',
                    alignItems: 'center', 
                    justifyContent: 'center',
                    py: 8,
                    px: 3,
                    textAlign: 'center',
                    bgcolor: 'background.paper',
                    border: '1px solid',
                    borderColor: 'divider',
                    borderTop: 'none'
                }}>
                    <Box sx={{ 
                        width: 80, 
                        height: 80, 
                        borderRadius: '50%', 
                        bgcolor: 'action.hover',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        mb: 3
                    }}>
                        <FilterListIcon sx={{ fontSize: 40, color: 'text.secondary' }} />
                    </Box>
                    <Typography variant="h6" color="text.primary" gutterBottom>
                        No data found
                    </Typography>
                    <Typography variant="body2" color="text.secondary" sx={{ maxWidth: 400 }}>
                        There are no records to display at the moment. Try adjusting your filters or check back later.
                    </Typography>
                </Box>
            )}
        </>
    );
};

const BanToggle = ({ record, resource }) => {
    const [update, { isLoading }] = useUpdate();
    const notify = useNotify();
    const theme = useTheme();
    const refresh = useRefresh();

    
    const [isBanned, setIsBanned] = useState(!!record.is_banned); // !! converts to boolean

    
    useEffect(() => {
        setIsBanned(!!record.is_banned);
    }, [record.is_banned]); 

    const handleToggle = (event) => {
        const newValue = event.target.checked;
        setIsBanned(newValue);

        update(
            resource,
            { id: record.id, data: { is_banned: newValue }, previousData: record },
            {
                onSuccess: () => {
                    notify(
                        newValue ? 'User has been banned' : 'User has been unbanned',
                        { type: 'success' }
                    );
                    refresh(); 
                },
                onError: (error) => {
                    setIsBanned(!newValue); 
                    notify(
                        `Error: Couldn't update ban status - ${error.message}`,
                        { type: 'error' }
                    );
                }
            }
        );
    };
    
    return (
        <FormControlLabel
            control={
                <Switch
                    checked={isBanned}
                    onChange={handleToggle}
                    disabled={isLoading}
                    color="error"
                    size="small"
                />
            }
            label={
                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                    {isBanned && (
                        <BlockIcon 
                            fontSize="small" 
                            sx={{ mr: 0.5, color: theme.palette.error.main }}
                        />
                    )}
                    <Typography variant="body2">
                        {isBanned ? "Banned" : "Ban"}
                    </Typography>
                </Box>
            }
            sx={{ m: 0 }}
        />
    );
};

const TruncatedTextField = ({ source, label, maxChars = 25 }) => {
    const record = useRecordContext();
    if (!record) return null;

    const value = record[source];
    
    // Show em dash for null, undefined, or empty string
    if (value === undefined || value === null || value === '') {
        return <span style={{ color: '#999' }}>—</span>;
    }

    const text = String(value);
    const isLong = text.length > maxChars;
    const display = isLong ? text.slice(0, maxChars).trimEnd() + '....' : text;

    const content = (
        <span
            style={{
                display: 'inline-block',
                maxWidth: '100%',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
            }}
        >
            {display}
        </span>
    );

    return (
        <Tooltip title={text}>
            <span>{content}</span>
        </Tooltip>
    );
};

// Let react-admin use the label in the header
TruncatedTextField.defaultProps = {
    addLabel: true,
};

// =============================================================================
// == CORRECTED UserList COMPONENT ==
// =============================================================================
const UserList = (props) => (
    <List 
        actions={<ListActions />}
        filters={[
            <SearchInput 
                source="q" 
                alwaysOn 
                placeholder="Search job seekers..." 
                sx={{ maxWidth: 400 }}
            />
        ]} 
        empty={false} // This prevents React Admin from showing its own empty component
        {...props}
    >
        <StyledDatagrid bulkActionButtons={<UserBulkActionButtons />} rowClick={false}>
            <FunctionField
                label="Name"
                sortBy="name"
                render={() => <ClickableNameField source="name" resource="users" maxChars={25} />}
            />
            <TruncatedTextField source="email" maxChars={28} />
            <TruncatedTextField source="college_name" label="College" maxChars={22} />
            <FunctionField
                label="Ban Status"
                sortable={false}
                render={(record) => <BanToggle record={record} resource="users" />}
            />
        </StyledDatagrid>
    </List>
);

const CompanyList = (props) => (
    <List 
        actions={<ListActions resource="companies" />}
        filters={[
            <SearchInput 
                source="q" 
                alwaysOn 
                placeholder="Search companies..." 
                sx={{ maxWidth: 400 }}
            />
        ]}
        empty={false} // This prevents React Admin from showing its own empty component
        {...props}
    >
        <StyledDatagrid bulkActionButtons={<CompanyBulkActionButtons />} rowClick={false}>
            <FunctionField
                label="Company Name"
                sortBy="company_name"
                render={() => <ClickableNameField source="company_name" resource="companies" maxChars={25} />}
            />
            <TruncatedTextField source="email" maxChars={30} />
            <TruncatedTextField source="industry" maxChars={35} />
            <FunctionField
                label="Ban Status"
                sortable={false}
                render={(record) => <BanToggle record={record} resource="companies" />}
            />
        </StyledDatagrid>
    </List>
);

const JobList = (props) => (
    <List 
        actions={<ListActions />}
        filters={[
            <SearchInput 
                source="q" 
                alwaysOn 
                placeholder="Search jobs..." 
                sx={{ maxWidth: 500 }}
            />
        ]} 
        empty={false} // This prevents React Admin from showing its own empty component
        {...props}
    >
        <StyledDatagrid bulkActionButtons={<JobBulkActionButtons />}>
            <TruncatedTextField
                source="title"
                label="Job Title"
                maxChars={30}
            />
            <TruncatedTextField
                source="company_name"
                label="Company"
                maxChars={20}
            />
            <TruncatedTextField
                source="job_type"
                label="Job type"
                maxChars={15}
            />
            <TruncatedTextField
                source="location"
                label="Location"
                maxChars={25}
            />
            <TruncatedTextField
                source="salary"
                label="Salary"
                maxChars={15}
            />
            <TextField source="total_vacancy" sortable={false} />
            <TextField source="filled_vacancy" sortable={false} />
            <TruncatedTextField
                source="status"
                label="Status"
                maxChars={10}
            />
        </StyledDatagrid>
    </List>
);

/* <<< DEFINE A SINGLE LIGHT THEME FOR THE ENTIRE APP >>>
const lightTheme = {
    ...defaultTheme,
    palette: {
        ...defaultTheme.palette,
        mode: 'light',
    },
};
*/

const App = () => (
    <Admin 
        dataProvider={customDataProvider} 
        authProvider={authProvider}
        dashboard={Dashboard}
        loginPage={CustomLoginPage}
        layout={CustomLayout}
        title="Admin Portal"
        requireAuth
        // theme={lightTheme} // Set the default theme
        // darkTheme={lightTheme} // Force the light theme even in dark mode
    >
        <Resource 
            name="users" 
            list={UserList} 
            icon={PeopleAltIcon} 
            options={{ label: 'Job Seekers' }} 
        />
        <Resource 
            name="companies" 
            list={CompanyList} 
            icon={BusinessIcon} 
        />
        <Resource 
            name="jobs" 
            list={JobList} 
            icon={WorkIcon} 
        />
    </Admin>
);

export default App;
