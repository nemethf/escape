#ifndef VNFS_H
#define VNFS_H
//ovs commands
#define OVS_OFCTL_COMMAND "ovs-ofctl"
#define OVS_VSCTL_COMMAND "ovs-vsctl"
//log definitions
#define INFO 0
#define WARNING 1
#define ERROR 2
#define LOG 4
#define LINK_UP 1
#define LINK_DOWN 0
#include <glib.h>

/*
 * This struct is devoted to store all data of a link/connection
 * gchar* vnf_dev - virtual ethernet device attached to the vnf
 * gchar* sw_dev - virtual ethernet device attached to the switch
 * gboolean connected - whether link is up (TRUE) or down (FALSE)
 * gchar* sw_id - switch id the link is connected to
 * gchar* sw_port - port of the switch
 */
typedef struct vnf_link
{
	gchar* vnf_dev;
	gchar* sw_dev;
	gboolean connected;
	gchar* sw_id;
	gchar* sw_port;
}vnf_link;



/*
 * This struct is devoted to give a data structure for storing a vnf with all
 * of its data
 * int pid - Process ID
 * GHashTable *links - a hashtable vnf_link struct (see above), where the key
 * is the vnf_port, e.g., 0, 1, 2, and the value is the vnf_link struct
 * gchar *control_ip - the control ip of the click/vnf module
 * gchar *control_port - the opened port for the click/vnf module
 * gchar *vnf_command - the linux shell command to start a click/vnf
 */
typedef struct vnf_data
{
	int pid;
	GHashTable *links;
	gchar *vnf_command;
	gchar *control_ip;
	gchar *control_port;
}vnf_data;



/*
 * This is a colorized logger function for standard information
 * int type - type of log (INFO, WARNING, ERROR) - predefined types!
 * gchar* msg - the message to print out
 */
void custom_log(int type, const gchar* msg);


/*
 * This function draws a green bar to stdout
 */
void log_info_bar(void);


/*
 * This function draws a red bar to stdout
 */
void log_error_bar(void);

/*
 * This function draws a yellow bar to stdout
 */
void log_warning_bar(void);

/*
 * This procedure initilialize the internal variable hashtable
 * (GHashTable *vnfs) used to store vnfs
 */
void vnf_initializer(void);


/*
 * This procedure creates a new vnf_link struct
 * return *vnf_link - the initiated vnf_link struct
 */
vnf_link* initLink();


/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure automatically creates a new VNF structure with empty data
 * for effective storing. It also generates a unique ID for the newly created
 * VNF.
 * int port_num - number of ports a vnf requires
 * return gchar* - the new unique id of the VNF, e.g, vnf_X
 */
gchar* createVNF();




/*
 * This process will start the VNF by the command that is already set to its
 * structure's vnf_command variable.
 * gchar* vnf_id - the id of the vnf
 * return gboolean - TRUE if everything went fine,
 * 					 FALSE if something went wrong
 */
gboolean startVNF(gchar* vnf_id);

/*
 * This procedure will connect the given vnf to the given switch via the given/
 * requested vnf_port
 * gchar* vnf_id - the id of the vnf
 * gchar* vnf_port - one of the vnf's available ports
 * gchar* switch_id - the id of the switch
 * return gchar* - the port number of the switch
 */
gchar* connectVNF(gchar* vnf_id, gchar* vnf_port, gchar* switch_id);


/*
 * This procedure will disconnect the given vnf_port of the given vnf
 * gchar* vnf_id - the id of the vnf, e.g., vnf_1
 * gchar* vnf_port - the port of the vnf, e.g., 0,1,2
 */
gboolean disconnectVNF(gchar* vnf_id, gchar* vnf_port);



/*
 * This procedure will gracefully stop a VNF
 * gchar vnf_id - the id of the vnf
 * return gboolean - TRUE if everythin went fine,
 * 					 FALSE if something went wrong
 */
gboolean stopVNF(gchar* vnf_id);



/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure removes a certain link with all its data from the hashtable
 * gchar* key - the key of the links hashtable
 * vnf_link* value - vnf_link struct as value
 */
void removeLink(gchar* key, vnf_link* link);




/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure adds a string element as a value to the given GHashTable
 * identified by a string key.
 * GHashTable *t - the hashtable object to insert the data
 * gchar *key - key
 * gchar *value - value
 * gboolean supress - TRUE = supress logging, FALSE - verbose mode
 */
void add_string_element(GHashTable *t, gchar *key, gchar *value, gboolean supress);


/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure adds a vnf_data typed struct element as a value to the given
 * GHashTable identified by a string key.
 * GHashTable *t - the hashtable object to insert the data
 * gchar *key - key
 * vnf_data *data - struct to be added
 *
 * return gboolean - FALSE if something went wrong
 * 					 TRUE if everything went fine
 */
gboolean addVNF(gchar *key, vnf_data *data);


/*
 * This helper function will print out all data of the links hashtable
 * gchar* key - the key in the hashtable
 * vnf_link* link - type of the value
 */
void print_links(gchar* key, vnf_link* link);


/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure prints all the data of all vnfs that have been started.
 * It is called by the iterating function of GLib, which looks like this:
 * g_hash_table_foreach(vnfs, (GHFunc) print_data, NULL);
 */
void print_data (gchar *key, vnf_data *value);


/*
 * Helper function to print all the elements of a given GSList object
 */
void print_list_data(GSList *l);


/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * Helper function to get a certain vnf as vnf_data struct
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * return vnf_data - the vnf and its data
 */
vnf_data* getVNF(gchar *vnf_id);



/*
 * This procedure returns the pid of the given vnf
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * return int - the pid of the vnf
 */
int getPid(gchar *vnf_id);



/*
 * This procedure sets the pid of the given vnf
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * gchar *pid - PID
 */
void setPid(gchar *vnf_id, int pid);




/*
 * This helper function returns the max value as a gchar of a list of numbers
 * stored as gchars.
 * It is called from function createVirtualEthernetPairs(), and is used to
 * determine the highest veth device (uny_X) id
 * return gchar* - highest id
 */
gchar* getHighestDeviceID(GSList* dev_list);


/*
 * This helper function creates a substring of a virtual ethernet pair
 * containing only the first or the second device id
 * gchar* veth_pair_as_char - virtual ethernet pair, e.g., uny_1-uny_2
 * int i - number of device (0 or 1)
 * return gchar* - device id
 */
gchar* subStringDeviceIdFromVirtualEthernetPair(gchar* veth_pair_as_char,
													   int i);


/*
 *     ---------------------- SYSTEM -------------------------
 * This procedure connects a device to a switch, by calling ovs_vsctl add port
 * command.
 * gchar* dev - the name of the device, e.g., uny_2
 * gchar* sw_id - the id of the switch, e.g., s3
 * return gchar* - status message of the execution
 */
gchar* connectVirtualEthernetDeviceToSwitch(gchar* dev, gchar* sw_id);



/*
 *     ---------------------- SYSTEM -------------------------
 * This procedure will actually bring up the virtual ethernet pairs, since
 * even if both ends of it are connected to some switches, they are in DOWN
 * state.
 * gchar* vnf_dev - the virtual ethernet device assigned to the vnf
 * gchar* sw_dev - the virtual ethernet device assigned to the switch
 * gint status - LINK_UP or LINK_DOWN
 * up
 * return gboolean - TRUE if everything went fine
 * 					 FALSE if something went wrong
 */
gboolean bringVirtualEthernetPairs(gchar* vnf_dev, gchar* sw_dev, gint status);



/*
 * This procedure will delete/remove the given port from a switch with
 * ovs-vsctl del-port command.
 * Deleting a port from ovs switch requires only the device id, not the port
 * number, therefore this function needs to be called by giving the
 * device id as an argument in order to remove it
 * gchar* veth_device - the device attached to one of the ports of the switch,
 * e.g, uny_0
 * return gboolean - TRUE if everything went fine
 * 					 FALSE if something went wrong
 *
 */
gboolean deleteSwitchPort(gchar* veth_device);



/*
 *     ---------------------- SYSTEM -------------------------
 * This procedure will create a practical veth pairs by system calls.
 * It also checks other existing veth pairs, and automatically determine, which
 * name should be assigned to the new pairs.
 * return GSList* - list of names of the newly created veth pairs in order to
 * set it for a vnf by addVirtualEthernetPairs(...) function
 */
gchar* createVirtualEthernetPairs(void);



/*
 *     ---------------------- SYSTEM -------------------------
 * This helper function will practically delete the veth pairs from the system
 * gchar* vnf_dev - vnf's device
 * gchar* sw_dev - switch's device
 */
void deleteVirtualEthernetPair(gchar* vnf_dev, gchar* sw_dev);



/*
 * This procedure gets a certain switch port assigned to a device id
 * gchar* sw_id - id of the switch
 * gchar* dev_id - device id, which for the port is assigned
 * return gchar* - port number
 */
gchar* getSwitchPort(gchar* sw_id, gchar* dev_id);


/*
 *     ---------------------- SYSTEM -------------------------
 * This function collects the ports and corresponding device ids of the given
 * switch
 * gchar* sw_id - id of the switch, e.g., s3
 * return GHashTable* - hashtable of the results ([port_num]=dev_id)
 */
GHashTable* getAllSwitchPorts(gchar* sw_id);


/*
 * This procedure gets the control port of the VNF
 * gchar* vnf_id - vnf id
 * return gchar* - control port
 */
gchar* getControlPort(gchar* vnf_id);

/*
 * This procedure sets the control port
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * gchar *port - control port
 */
void setControlPort(gchar *vnf_id, gchar *port);


/*
 * This procedure gets the control ip of the VNF
 * gchar* vnf_id - vnf id
 * return gchar* - control IP
 */
gchar* getControlIP(gchar* vnf_id);




/*
 * This procedure sets the control IP
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * gchar *ip_addr - control IP address
 */
void setControlIP(gchar *vnf_id, gchar *ip_addr);



/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure removes a certain vnf with all its data from the hashtable
 * gchar *vnf_id - vnf id
 */
void removeVNF(gchar *vnf_id);



/*
 * This procedure sets the click/vnf shell command
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * gchar *command - the linux shell command
 */
void setVNFCommand(gchar *vnf_id, gchar *command);


/*
 * This procedure gets the command of the vnf
 * gchar* vnf_id - the id of the vnf
 * return gchar* - the command
 */
gchar* getVNFCommand(gchar *vnf_id);

/*
 * This procedure prints out the vnfs and their data
 */
void printVNFs(void);

/*
 * This procedure returns the number of vnfs that are stored
 * return gint - number of vnfs
 */
gint getNumberOfVNFs(void);

#endif /* VNFS_H */
