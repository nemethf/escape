#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>


// in order to create new processes
#include <unistd.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <signal.h>

#include "vnfs.h"
#include "colors.h"


GHashTable *vnfs = NULL;

/*
 * Compatibility code for older glib.
 */
static inline
gboolean hash_table_insert(GHashTable *hash_table,
			   gpointer key,
			   gpointer value)
{
#if GLIB_CHECK_VERSION (2, 39, 0)
    return g_hash_table_insert(hash_table, key, value);
#else
    g_hash_table_insert(hash_table, key, value);
    return 1;
#endif
}

/*
 * This is a colorized logger function for standard information
 * int type - type of log (INFO, WARNING, ERROR) - predefined types!
 * gchar* msg - the message to print out
 */
void custom_log(int type, const gchar* msg)
{
	switch(type)
	{
	case INFO:
		g_print("%s[INFO]%s %s\n", green_bold, none, msg);
		break;
	case WARNING:
		g_print("%s[WARNING]%s %s\n", yellow_bold, none, msg);
		break;
	case ERROR:
		g_print("%s[ERROR]%s %s\n", red_bold, none, msg);
		break;
	case LOG:
		g_print("%s[LOG]%s %s\n", blue_bold, none, msg);
		break;
	default:
		g_print("%s\n",  msg);
	}
}

/*
 * This function draws a green bar to stdout
 */
void log_info_bar(void)
{
	g_print("%s%s\n", green_bar,none);
}

/*
 * This function draws a red bar to stdout
 */
void log_error_bar(void)
{
	g_print("%s%s\n", red_bar,none);
}

/*
 * This function draws a yellow bar to stdout
 */
void log_warning_bar(void)
{
	g_print("%s%s\n", yellow_bar,none);
}




/*
 * This procedure initilialize the internal hashtable
 * (GHashTable *vnfs) used to store vnfs
 */
void vnf_initializer(void)
{
	vnfs = g_hash_table_new_full (g_str_hash, g_str_equal, g_free, g_free);
	custom_log(LOG, "VNF datastructure initialized");
}


/*
 * This procedure creates a new vnf_link struct
 * return *vnf_link - the initiated vnf_link struct
 */
vnf_link* initLink(void)
{
	//initializing vnf's link's struct
	vnf_link *link;
	//allocating space for vnf_link
	link = g_malloc(sizeof *link);

	//initializing link
	link->vnf_dev = NULL;
	link->vnf_dev_mac = NULL;
	link->sw_dev = NULL;
	link->connected = FALSE;
	link->sw_id = NULL;
	link->sw_port = NULL;



	return link;
}


/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure automatically creates a new VNF structure with empty data
 * for effective storing. It also generates a unique ID for the newly created
 * VNF.
 * int port_num - number of ports a vnf requires
 * return gchar* - the new unique id of the VNF, e.g, vnf_X
 */
gchar* createVNF(void)
{
	//The new unique id of the vnf
	gchar* new_ID = NULL;

	//check whether there exists any VNF of not
	if(g_hash_table_size(vnfs) == 0)
	{
		//There is no VNF yet
		new_ID = g_strconcat("vnf_", "1", NULL);

	}
	else
	{
		/* if any VNF already exists in the hashtable, we need to check all ids
		in order to ensure that a newly created id will be unique as well */


		//for storing the highest vnf number
		gint highestNumber = 0;
		//getting the keys from hashtable 'vnfs'
		GList* ids = g_hash_table_get_keys(vnfs);
		//temporary variable for iterating the list of the keys
		GList* iterator = NULL;
		for(iterator = ids; iterator; iterator = iterator->next)
		{
			//we handling everything as gchar*, since it is easier
			gchar* vnf_number = NULL;

			//tokenizing vnf ids
			//we need to create a new variable
			gchar* current_vnf_id = g_strdup((gchar*)iterator->data);

			//this will produce 'vnf' from 'vnf_X'
			vnf_number = strtok(current_vnf_id, "_");

			//this will produce 'X'
			vnf_number = strtok(NULL, "_");

			//convert it to int in order to compare the values
			gint vnf_number_as_int = atoi(vnf_number);

			//comparing
			if(vnf_number_as_int > highestNumber)
			{
				//updating highest number
				highestNumber = vnf_number_as_int;
			}
		}

		//freeing temporary lists
		g_list_free(iterator);
		g_list_free(ids);

		//new id should be higher than the found maximum
		highestNumber++;


		//assembling the new vnf id
		new_ID = g_strconcat("vnf_", g_strdup_printf("%d",highestNumber), NULL);

	}


	//creating an empty vnf_data structure and initializing its variables
	vnf_data *data;
	//allocating space for vnf_data structure
	data = g_malloc(sizeof *data);

	//initializing the variables of the vnf structure

	data->pid = -1;
	data->control_ip = NULL;
	data->control_port = NULL;
	data->vnf_command = NULL;
	data->options = g_hash_table_new_full(g_str_hash,
										  g_str_equal,
										  g_free,
                                          g_free);


	data->links = g_hash_table_new_full(g_str_hash,
										g_str_equal,
										g_free,
										g_free);





	//Add the created vnf to the main hashtable that stores all vnfs
	addVNF(new_ID, data);


	//pass back the ID of the newly created vnf
	return new_ID;
}


/*
 * This process will start the VNF by the command that is already set to its
 * structure's vnf_command variable.
 * gchar* vnf_id - the id of the vnf
 * return gboolean - TRUE if everything went fine,
 * 					 FALSE if something went wrong
 */
gboolean startVNF(gchar* vnf_id)
{
	//getting the vnf
	vnf_data *found_vnf = getVNF(vnf_id);



	//concatenating the new command by iterating through vnf's
    //hashtable options
    custom_log(INFO, "Assembling command...");

    //get basic command
    gchar* command = g_strdup_printf("%s ", found_vnf->vnf_command);

    //get options
    GHashTableIter iter;
    gpointer key, value;
    g_hash_table_iter_init(&iter, found_vnf->options);
    while(g_hash_table_iter_next(&iter, &key, &value))
    {
        //checking whether options have no NULL values
        if(value == NULL)
        {
            //there is a value of NULL, we do not concatenate...continue loop
            continue;
        }

        //concatenate options to command
        command = g_strconcat(command,
                              g_strdup_printf("%s",(gchar*)key),
                              "=",
                              g_strdup_printf("%s ",(gchar*)value),
                              NULL);


    }

    //concatenate vnf_id, control_port and control_ip to command
    //checking whether control port is set
    if(found_vnf->control_port != NULL)
    {
        command = g_strconcat(
                    command,
                    g_strdup_printf("csPort=%s ", found_vnf->control_port),
                    NULL);
    }
    //checking whether control_ip is set
    if(found_vnf->control_ip != NULL)
    {
        command = g_strconcat(
                            command,
                            g_strdup_printf("csIP=%s ", found_vnf->control_ip),
                            NULL);
    }

    //concatenate vnf_id to command
    command = g_strconcat(command,
                  g_strdup_printf("vnf_id=%s ", vnf_id),
                  NULL);


    //concatenate links' vnf_devs
    //getting the keys of hashtable links
    GList* links_keys = g_hash_table_get_keys(found_vnf->links);
    GList* it = NULL;
    //iterating through got keys
    for(it = links_keys; it; it=it->next)
    {
        //concatenate keys (that are 0,1,2...) to command,
        //and also concatenate the corresponding vnf_dev field from
        //the links' structure
        command = g_strconcat(command,
                      g_strdup_printf("dev_%s=", (gchar*)it->data),
                      g_strdup_printf("%s ",
                              ((vnf_link*)(g_hash_table_lookup(found_vnf->links, (gchar*)it->data)))->vnf_dev),
                              NULL);

    }


    //OK, we got everything for the command...set it back to the original one
    found_vnf->vnf_command = g_strdup_printf("%s", command);


    /*
     * the signal() command tries to avoid blocking main thread!
     *
     * otherwise, yangcli/netconf client also waits for termination of
     * child process
     *
     * This signal also makes it possible to avoid <defunct> child
     * processes after those children was killed by system calls
     *
     * However, after this command, it doesn't wait for the
     * termination of its children, so stopping a chain and restarting
     * will fail.  So, we commented the line out for the time being.
     */
    //signal(SIGCHLD, SIG_IGN);

	//this PID is the agent's PID, not the VNF's
	int processID;
	//checking whether forking was successful
	if((processID = fork()) == 0 )
	{
		//the child process
		printf("-------- CHILD PROCESS\n\n");

				      

		custom_log(INFO, g_strdup_printf("The command is: %s", found_vnf->vnf_command));


		//staring VNF
		int errorCode = execl("/bin/sh",
							  "sh",
							  "-c",
							  found_vnf->vnf_command,
							   (char *)NULL);

		//if everything went fine, we do not reach this point
		custom_log(ERROR, g_strdup_printf("The result of the execution is %d",
										  errorCode));
		_exit(127);
	}
	else if(processID < 0)
	{
		//error during fork
		custom_log(ERROR, "An error occurred during forking...");
	}
	else
	{
		//parent process
		custom_log(LOG, g_strdup_printf("Command (%s) was successfully forked",
										 found_vnf->vnf_command));
		custom_log(LOG, g_strdup_printf("The VNF's PID is: %d", processID));
		found_vnf->pid = processID;

	}


	return TRUE;
}



/* -------------------- DATASTRUCTURE -------------------------
 * This procedure adds a new link struct to a vnf datastructure
 * gchar* vnf_id - the id of the vnf
 * gchar* key - the desired key in the hash table
 * vnf_link*
 */
static
void addLinkToVNF(gchar* vnf_id, gchar* key, vnf_link* link)
{
	vnf_data *found_vnf = getVNF(vnf_id);
	int success  =  hash_table_insert(found_vnf->links,
										g_strdup (key),
										link);
	if(success)
	{
		//if everything went fine
		custom_log(INFO, g_strdup_printf("Link is added to %s", vnf_id));
	}
	else
	{
		//if an error occurred
		custom_log(ERROR, g_strdup_printf("Error during adding link to %s",
										   vnf_id));
	}

}

/*
 * This procedure will connect the given vnf to the given switch via the given/
 * requested vnf_port
 * gchar* vnf_id - the id of the vnf
 * gchar* vnf_port - one of the vnf's available ports
 * gchar* switch_id - the id of the switch
 * return gchar* - the port number of the switch
 */
gchar* connectVNF(gchar* vnf_id, gchar* vnf_port, gchar* switch_id)
{

	//getting the vnf
	vnf_data *found_vnf = getVNF(vnf_id);

	//for the link structure
	vnf_link *l = NULL;

	//this is the return value. The switch port will be determined by an
	//ovs-vsctl command
	gchar* sw_port = NULL;

	//checking whether a link is existed
	if(g_hash_table_lookup_extended(found_vnf->links, vnf_port, NULL, NULL) ==
		FALSE)
	{
		//create new link and connecting
		l = initLink();
		gchar* uny_pair = createVirtualEthernetPairs();
		gchar* vnf_dev = subStringDeviceIdFromVirtualEthernetPair(uny_pair,0);
		gchar* sw_dev = subStringDeviceIdFromVirtualEthernetPair(uny_pair,1);

		sw_port = connectVirtualEthernetDeviceToSwitch(sw_dev,switch_id);

		//setting link params
		l->vnf_dev = g_strdup(vnf_dev);
		l->vnf_dev_mac = g_strdup(getMacAddress(vnf_dev));
		l->sw_dev = g_strdup(sw_dev);
		l->sw_id = g_strdup(switch_id);
		l->sw_port = g_strdup(sw_port);

		//bringing up virtual ethernet pairs
		if(bringVirtualEthernetPairs(vnf_dev, sw_dev, LINK_UP))
		{
			//bringing up was successful
			l->connected = TRUE;
			custom_log(INFO, g_strdup_printf("%s (%s) is connected to switch %s"
											 " (%s)",
											 vnf_id,
											 vnf_dev,
											 switch_id,
											 sw_dev));
		}
		else
		{
			//something went wrong during bringing up interfaces
			l->connected = FALSE;
		}

		//adding link to vnf's datastructure
		addLinkToVNF(vnf_id, vnf_port, l);

	}
	else
	{
		//the given link already existed

		//getting the link structure
		l = g_hash_table_lookup(found_vnf->links, vnf_port);

		//checking whether the switch_id assigned to the link is equal to
		//the given switch_id
		if(g_strcmp0(l->sw_id, switch_id) == 0)
		{
			//RECONNECT
			if(bringVirtualEthernetPairs(l->vnf_dev, l->sw_dev, LINK_UP))
			{
				//bringing up was successful
				l->connected = TRUE;
				custom_log(INFO, g_strdup_printf("%s (%s) is reconnected to "
												 "switch %s (%s)",
												 vnf_id,
												 l->vnf_dev,
												 switch_id,
												 l->sw_dev));
			}
			else
			{
				//something went wrong during bringing up interfaces
				l->connected = FALSE;
			}

			sw_port = l->sw_port;

		}
		else
		{
			//TODO: if a connection entry is already existed for the given
			//		vnf_port, but the assigned switch_id is different than
			//		the given switch_id
			sw_port = NULL;
			custom_log(ERROR, "WRONG arguments have been set for connect func");
		}
	}

	return sw_port;

}


/*
 * This procedure will disconnect the given vnf_port of the given vnf
 * gchar* vnf_id - the id of the vnf, e.g., vnf_1
 * gchar* vnf_port - the port of the vnf, e.g., 0,1,2
 */
gboolean disconnectVNF(gchar* vnf_id, gchar* vnf_port)
{
	//getting the vnf
	vnf_data *found_vnf = getVNF(vnf_id);

	//getting the link structure
	vnf_link *l = g_hash_table_lookup(found_vnf->links, vnf_port);

	//checking whether vnf_port exists
	if(l == NULL)
	{
		//given vnf_port does not exist
		custom_log(ERROR, g_strdup_printf("%s has no link identified by %s",
										  vnf_id, vnf_port));
		return FALSE;
	}

	//disconnecting interfaces
	if(bringVirtualEthernetPairs(l->vnf_dev, l->sw_dev, LINK_DOWN))
	{
		l->connected = FALSE;
		return TRUE;
	}
	else
	{
		return FALSE;
	}
}




/*
 * This procedure will gracefully stop a VNF
 * gchar vnf_id - the id of the vnf
 * return gboolean - TRUE if everythin went fine,
 * 					 FALSE if something went wrong
 */
gboolean stopVNF(gchar* vnf_id)
{
	log_error_bar();
	//getting the vnf
	vnf_data *found_vnf = getVNF(vnf_id);

	custom_log(INFO, g_strdup_printf("[VNF DATASTRUCTURE] Deleting all data of %s",
							  vnf_id));
	//clearing some simple variables - practical freeing will handled by GLIB
	//set the gchar* that holds vnf command to NULL
	found_vnf->vnf_command = NULL;
	custom_log(INFO, "\tCommand is deleted");


	//set the gchar* that holds vnf's control port to NULL
	found_vnf->control_port = NULL;
	custom_log(INFO, "\tControl port is deleted");

	//free the gchar* that holds vnf's control IP
	found_vnf->control_ip = NULL;
	custom_log(INFO, "\tControl IP is deleted");

	custom_log(INFO, "\tKilling VNF");
	//assembling killing command with pstree
	//pstree gives a tree of the processes and all its children, grandchildren
	//and so on
	//with some fine grepping its stdout and pass it to kill will definitely
	//terminate the whole process tree
	gchar* command = g_strconcat(
						"kill `pstree -p ",
						g_strdup_printf("%d ",found_vnf->pid),
						" |grep -oP \'(\?<=\\()[0-9]+(\?=\\))\' | sort -r` ",
						NULL);
	custom_log(LOG, g_strdup_printf("Kill command: %s", command));
	//killing process
//	int status = system(command);
	system(command);
	//checking whether kill was successful
	//DON'T KNOW WHY, BUT SYSTEM() RETURNS -1, BUT PROCESS TREE HAS BEEN
	//SUCCESSFULLY TERMINATED, THEREFORE THE FOLLOWING PART IS COMMENTED
//	if(status == 0)
//	{
//		custom_log(INFO, g_strdup_printf("VNF (pid: %d) was successfully killed!",
//						 	 	 	 	 found_vnf->pid));
//
//	}
//	else
//	{
//
//		custom_log(ERROR, g_strdup_printf("Error occurred during killing VNF (pid: %d)",
//						 	 	 	 	 found_vnf->pid));
//
//		//checking whether pid is real
//		if(status == 1 || status == 256)
//		{
//			//Process ID not found
//			custom_log(ERROR, g_strdup_printf("There is no PID like %d",found_vnf->pid));
//		}
//
//		//print return value
//		custom_log(ERROR, g_strdup_printf("Return value of pkill: %d", status));
//
//		return FALSE;
//	}

	//removing interfaces and ports
	g_hash_table_foreach(found_vnf->links, (GHFunc)removeLink, NULL);
	//removing links
	g_hash_table_remove_all(found_vnf->links);
	//destroy hashtable
	g_hash_table_destroy(found_vnf->links);


	//set the gchar* that holds vnf's PID to -1
	found_vnf->pid = -1;


	//removing vnf datastructure from the main vnf hashtable
	removeVNF(vnf_id);

	return TRUE;

}


/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure removes a certain link with all its data from the hashtable
 * gchar* key - the key of the links hashtable
 * vnf_link* value - vnf_link struct as value
 */
void removeLink(__attribute__((unused)) gchar* key, vnf_link* link)
{
	//bring down virtual ethernet pairs
	bringVirtualEthernetPairs(link->vnf_dev,link->sw_dev,LINK_DOWN);
	//deleting switch port
	deleteSwitchPort(link->sw_dev);
	//deleting practical interfaces
	deleteVirtualEthernetPair(link->vnf_dev, link->sw_dev);
}


/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure is devoted to add options (sent by netconf client at the
 * initialization phase) to the corresponding vnf's datastructure
 * gchar* vnf_id - the id of the vnf
 * gchar* option_name - the key in the vnf's options hashtable
 * gchar* option_value - the value assigned to the key in the
 * vnf's options hashtable
 */
void addOptionsToVNF(gchar* vnf_id, gchar* option_name, gchar* option_value)
{
    //getting the vnf
    vnf_data *found_vnf = getVNF(vnf_id);

    //after we got the vnf and its data, we only need to call our helper func.
    add_string_element(found_vnf->options, option_name, option_value, TRUE);
}



/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure adds a string element as a value to the given string key in
 * the given GHashTable
 * GHashTable *t - the hashtable object to insert the data
 * gchar *key - key
 * gchar *value - value
 * gboolean supress - TRUE = supress logging, FALSE - verbose mode
 */
void add_string_element(GHashTable *t, gchar *key, gchar *value, gboolean supress)
{

	if(!supress)
	{
	//verbose mode ON
		custom_log(INFO, g_strdup_printf("[VNF_DATASTRUCTURE] "
								  "Adding the following key-value pair:%s - %s",
								  key,
                                  value));
	}
    //I do not know the reason, probably a bug, but if a key exists then the
    //hash_table_insert() does not update it, but rather cause error.
    //However, its documentation says that it should do this thing
    if(g_hash_table_contains(t,key))
    {
    	//Hashtable has already an entry with the given key
        custom_log(WARNING, g_strdup_printf("[VNF_DATASTRUCTURE] "
        							"%s as key already exists!\n"
        					  	    "We need to remove it first!",
        					  	    key));
        //remove the key and its corresponding data
        g_hash_table_remove(t, key);
    }

    //Inserting the new key-value pair
    int success  =  hash_table_insert(t,
                                        g_strdup (key),
                                        g_strdup(value));

    if(success)
    {
    	//if everything went fine
    	if(!supress)
    	{
    		//verbose mode ON
    		custom_log(INFO, g_strdup_printf("[VNF_DATASTRUCTURE] "
    								 "Key-Value pair (%s:%s) was "
    								 "successfully added!",
                                     key,
                                     value));
    	}
    }
    else
    {
    	//if something went wrong, we do not care about verbose mode, we always
    	//print out that an error occurred
    	custom_log(ERROR, g_strdup_printf("[VNF_DATASTRUCTURE] "
    							  "Error during adding Key-Value pair (%s:%s)",
    						   	  key,
    						   	  value));
    }
}


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
gboolean addVNF(gchar *key, vnf_data *data)
{

	//adding a new element
    int success  =  hash_table_insert(vnfs,
										g_strdup (key),
										data);
	if(success)
	{
		//if everything went fine
		custom_log(INFO, "[VNF_DATASTRUCTURE] "
				 "VNF is added");
	}
	else
	{
		//if an error occurred
		custom_log(ERROR, "[VNF_DATASTRUCTURE] "
				  "Error during adding VNF");
	}

	return success;
}



/*
 * This helper function will print out all data of the links hashtable
 * gchar* key - the key in the hashtable
 * vnf_link* link - type of the value
 */
void print_links(gchar* key, vnf_link* link)
{
	g_print("\t\t%s:\n", key);
	g_print("\t\t  vnf_dev: %s\n", link->vnf_dev);
	g_print("\t\t  vnf_dev_mac: %s\n", link->vnf_dev_mac);
	g_print("\t\t  sw_dev: %s\n", link->sw_dev);
	g_print("\t\t  sw_id: %s\n", link->sw_id);
	g_print("\t\t  sw_port: %s\n", link->sw_port);
	g_print("\t\t  connected: %d\n", link->connected);
}


/*
 * This helper function will print out a hashtable options of a vnf
 * gchar* option_name - the key in the hashtable
 * gchar* option_value - the value assigned to the key
 */
void print_options(gchar* option_name, gchar* option_value)
{
    g_print("\t\t%s = %s\n", option_name, option_value);
}


/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure prints all the data of all vnfs that have been started.
 * It is called by the iterating function of GLib, which looks like this:
 * g_hash_table_foreach(vnfs, (GHFunc) print_data, NULL);
 */
void print_data (gchar *key, vnf_data *value)
{
    //print green bar as a separator
    log_info_bar();


    g_print("%s:\n",key);

    //PID
    g_print("\tPID = ");
    if(value->pid != 0)
    {
    	g_print("%d\n", value->pid);
    }
    else
    {
    	g_print("NULL\n");
    }



    //links
    g_print("\tLinks: \n");
    if(value->links != NULL)
    {
    	if(g_hash_table_size(value->links) == 0)
    	{
    		g_print("EMPTY\n");
    	}
    	else
    	{
    		g_hash_table_foreach(value->links,
    							 (GHFunc) print_links,
    							 NULL);
    	}
    }
    else
    {
    	g_print("NULL\n");
    }


    //control IP
    g_print("\tControl IP = ");
    if(value->control_ip != NULL)
    {
    	g_print("%s\n", value->control_ip);
    }
    else
    {
    	g_print("NULL\n");
    }



    //control port
    g_print("\tControl Port = ");
    if(value->control_port != NULL)
    {
    	g_print("%s\n", value->control_port);
    }
    else
    {
    	g_print("NULL\n");
    }


    g_print("\tClick/VNF command = ");
    if(value->vnf_command != NULL)
    {
    	g_print("%s\n", value->vnf_command);
    }
    else
    {
    	g_print("NULL\n");
    }


    //options
    g_print("\tOptions: \n");
    if(value->links != NULL)
    {
        if(g_hash_table_size(value->options) == 0)
        {
            g_print("EMPTY\n");
        }
        else
        {
            g_hash_table_foreach(value->options,
                                 (GHFunc) print_options,
                                 NULL);
        }
    }
    else
    {
        g_print("NULL\n");
    }


    //print green bar as a separator
    log_info_bar();
}



/*
 * Helper function to print all the elements of a given GSList object
 */
void print_list_data(GSList *l)
{


	GSList *iterator = NULL;
    for(iterator = l; iterator; iterator = iterator->next)
    {
    	if(iterator->data != NULL)
    	{
			g_print(iterator->data);
			if(iterator->next != NULL)
			{
				g_print(", ");
			}
			else
			{
				g_print("\n");
			}
    	}
    	else
    	{
    		g_print("NULL\n");
    	}
    }


}


/*
 * This procedure prints the data of a simple GHashTable, which consists of
 * keys of type gchar* and values of type gchar*
 * gchar* key - key of the GHashTable
 * gchar* value - value of the GHashTable
 */
void print_hashtable_values_as_gchar(gchar* key, gchar* value)
{
	g_print("\t[%s] = %s\n", key, value);
}

/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * Helper function to get a certain vnf as vnf_data struct
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * return vnf_data - the vnf and its data
 */
vnf_data* getVNF(gchar *vnf_id)
{
	vnf_data *found_vnf;
	found_vnf = g_hash_table_lookup(vnfs,vnf_id);
	if(found_vnf == NULL)
	{
		custom_log(ERROR, g_strdup_printf("The given vnf (%s) does not exist!",
								  vnf_id));
		return NULL;
	}
	return found_vnf;
}


/*
 * This procedure returns the pid of the given vnf
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * return int - the pid of the vnf
 */
int getPid(gchar *vnf_id)
{
	//get the actual vnf data
	vnf_data *found_vnf = getVNF(vnf_id);

	//get vnf's PID
	return found_vnf->pid;
}


/*
 * This procedure sets the pid of the given vnf
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * gchar *pid - PID
 */
void setPid(gchar *vnf_id, int pid)
{
	//get the actual vnf data
	vnf_data *found_vnf = getVNF(vnf_id);

	//set PID
	found_vnf->pid = pid;
}


/*
 * This procedure gets the given vnf's hashtable links
 * gchar* vnf_id - the id of the vnf
 * return GHashTable* - the hashtable links of the given vnf's
 */
GHashTable* getLinksHashtable(gchar* vnf_id)
{
	//get the actual vnf data
	vnf_data *found_vnf = getVNF(vnf_id);

	return found_vnf->links;
}


/*
 * This helper function returns the max value (as a gchar) of a list of numbers
 * (stored as gchars).
 * It is called from function createVirtualEthernetPairs(), and is used to
 * determine the highest veth device (uny_X) id
 * return gchar* - highest id
 */
gchar* getHighestDeviceID(GSList* dev_list)
{
	//iterator for iterating the given list
	GSList *iterator = NULL;

	//we set a current highest device id to -1, and it will be updated
	//during the process if a higher one was found
	gchar *current_max_value = g_strdup("-1");

	for(iterator = dev_list; iterator; iterator = iterator->next)
	{
		//iterating the dev_list list

		//comparing actual dev id with the currently highest value
		if(atoi(iterator->data) > atoi(current_max_value))
		{
			//if we found a highest device id, we update the currently known one
		    g_free(current_max_value);
			current_max_value = g_strdup((gchar*)iterator->data);
		}
	}
	//freeing the temprary iterator
	g_slist_free(iterator);


	return current_max_value;
}

/*
 * This helper function creates a substring of a virtual ethernet pair
 * containing only the first or the second device id
 * gchar* veth_pair_as_char - virtual ethernet pair, e.g., uny_1-uny_2
 * int i - number of device (0 or 1)
 * return gchar* - device id
 */
gchar* subStringDeviceIdFromVirtualEthernetPair(gchar* veth_pair_as_char, int i)
{
	gchar* dev = NULL;
	//checking whether the given veth pair is NULL
	if(veth_pair_as_char == NULL)
	{
		//if it is NULL
		custom_log(ERROR, "No virtual ethernet pair was given");
		return dev;
	}
	//checking whether the desired device number is in the interval of [0,1]
	if(i < 0 || i > 1)
	{
		//the desired device number is out of the interval [0,1]
		custom_log(ERROR, "Wrong Device number, use 0 for the first one, "
				  "and 1 for the second one");
		return dev;
	}

	//for tokenizing the given veth pair
	gchar* tmp = g_strdup(veth_pair_as_char);
	//tokenize - this will produce uny_X, from uny_X-uny_Y
	dev = strtok(tmp,"-");

	//checking which device is needed
	if(i == 1)
	{
		//if we need the second device, we tokenize it further
		//this will produce uny_Y
		dev = strtok(NULL,"-");
	}

	return dev;
}


/*
 *     ---------------------- SYSTEM -------------------------
 * This procedure connects a device to a switch, by calling ovs_vsctl add-port
 * command.
 * gchar* dev - the name of the device, e.g., uny_2
 * gchar* sw_id - the id of the switch, e.g., s3
 * return gchar* - switch port where the device has been attached
 */
gchar* connectVirtualEthernetDeviceToSwitch(gchar* dev, gchar* sw_id)
{
	gchar* switch_port = NULL;

	//assembling the command
	gchar* command = g_strconcat(OVS_VSCTL_COMMAND,
								 " add-port ",
								 sw_id,
								 " ",
								 dev,
								 NULL);

	//executing the command
	int status = system(command);
	//checking whether execution was successful
	if(status == 0)
	{
		//if everything went fine (return value of the command is 0)
		custom_log(INFO, g_strdup_printf("Device %s is connected to switch %s",
								  dev,
								  sw_id));

		//get the newly associated port number of the connected device
		switch_port = getSwitchPort(sw_id,dev);
	}
	else
	{
		//something went wrong during executing the command
		custom_log(ERROR, g_strdup_printf("An error occurred during connecting device %s"
								  " to switch %s",
								  dev,
								  sw_id));
	}

	//we can free command, since we do not need anymore
	g_free(command);

	return switch_port;

}


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
gboolean bringVirtualEthernetPairs(gchar* vnf_dev, gchar* sw_dev, gint status)
{
	//setting up the status
	const gchar* st = "";
	if(status == LINK_DOWN)
	{
		st = " down ";
	}
	else if(status == LINK_UP)
	{
		st = " up ";
	}
	else
	{
		//status information was not correctly set
		return FALSE;
	}


	//assembling the first bring-up command
	gchar* command_1 = g_strconcat("ip link set ",
					 vnf_dev,
					 st,
					 NULL);

	//executing the first bring-up command
	int returnValue = system(command_1);
//	custom_log(LOG, g_strdup_printf("Return value: %d", returnValue));
	//checking whether execution was successful
	if(returnValue == 0)
	{
		//if everything went fine (return value of the command is 0)
		custom_log(INFO, g_strdup_printf("Device %s has been brought %s",
								  	  	  vnf_dev, st));

	}
	else
	{
		//something went wrong during executing the command
		custom_log(ERROR, g_strdup_printf("An error occurred during bringing %s"
								  " device %s",
								  st,
								  vnf_dev));
		return FALSE;
	}
	//we can free command_1, since we do not need anymore
	g_free(command_1);




	//assembling the second command
	gchar* command_2 = g_strconcat("ip link set ",
						  sw_dev,
						  st,
						  NULL);

	//executing the first bring-up command
	returnValue = system(command_2);
	//checking whether execution was successful
	if(returnValue == 0)
	{
		//if everything went fine (return value of the command is 0)
		custom_log(INFO, g_strdup_printf("Device %s has been brought %s",
								  	  	  sw_dev,
								  	  	  st));

	}
	else
	{
		//something went wrong during executing the command
		custom_log(ERROR, g_strdup_printf("An error occurred during bringing %s"
								  " device %s",
								  st,
								  sw_dev));
		return FALSE;
	}
	//we can free command_1, since we do not need anymore
	g_free(command_2);


	return TRUE;

}



/*
 *     ---------------------- SYSTEM -------------------------
 *
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
gboolean deleteSwitchPort(gchar* veth_device)
{
	//assembling the command
	gchar* command = g_strconcat(
					OVS_VSCTL_COMMAND,
					" del-port ",
					veth_device,
					NULL);

	//running the command
	int status = system(command);

	//command was successfully executed
	if(status == 0)
	{
		custom_log(
			   INFO,
			   g_strdup_printf("%s was successfully deleted from the switch",
							   veth_device));
		return TRUE;
	}
	else
	{
		custom_log(ERROR, g_strdup_printf("Error occurred during deleting %s "
								  " from the switch",
								  veth_device));
		return FALSE;
	}

}


/*
 *     ---------------------- SYSTEM -------------------------
 * This helper function is devoted to get the MAC address of the given device
 * gchar* device - the device which MAC address is needed to know
 * return gchar* - the MAC address
 */
gchar* getMacAddress(gchar* device)
{
    //a line for stdout
    char path[100];

    //for found mac address, e.g., 7a:5c:37:75:23:d8
    gchar *mac = g_strdup("");

    //for running a command and read its stdout
    FILE *get_mac;

    //assembling the command - here we use grep and awk!
    gchar* command = g_strdup_printf("ifconfig -a |grep %s|awk '{print $5}'",
                                     device);

    //run the command
    get_mac = popen(command, "r");

    //checking that command was run successfully
    if(get_mac == NULL)
    {
        custom_log(ERROR, "Failed to run command");
        return NULL;
    }

    //command execution succeeded
    else
    {
        //reading stdout
        while(fgets(path,sizeof(path)-1, get_mac) != NULL)
        {
            //only one line will be given with the MAC address shown only
            //strtok is used to remove the trailing new_line indicator
            mac = g_strdup_printf("%s", strtok(path,"\n"));
        }
    }

    //close FILE
    pclose(get_mac);

    //freeing command, we do not need it anymore
    g_free(command);

    //return the found mac address
    return mac;

}


/*
 *     ---------------------- SYSTEM -------------------------
 * This procedure will create a practical veth pairs by system calls.
 * It also checks other existing veth pairs, and automatically determine, which
 * name should be assigned to the new veth pairs.
 * return gchar* - veth_pair_as_char consisting of the newly created veth pairs
 * in order to set it for a vnf by addVirtualEthernetPairs(...) function
 */
gchar* createVirtualEthernetPairs(void)
{

	//for storing all the uny_X devices' numbers (X)
	GSList *device_numbers = NULL;

	//a line for stdout
	char path[100];

	//found device, e.g., uny_3
	gchar *dev;

	//for running a command and read its stdout
	FILE *get_veths;


	//first we need to get actual uny_X devices
	get_veths = popen("ip link | grep uny| cut -d ' ' -f 2", "r");
	//the result is like: 'uny_2:'

	//checking that command was run successfully
	if(get_veths == NULL)
	{
		custom_log(ERROR, "Failed to run command");

	}
	//command execution succeeded
	else
	{
		//reading stdout
		while(fgets(path,sizeof(path)-1, get_veths) != NULL)
		{

			//this will produce 'uny' from 'uny_X:'
			dev = strtok(path,"_");

			//this will produce the number (id) after 'uny_' without the colon
			dev = strtok(NULL,":");
//			g_print(dev);
			//we store them as gchars, since they can be easier handled in a
			//GSList*

			//adding found device numbers (ids) to a list
			device_numbers = g_slist_append(
										device_numbers,
										g_strdup(dev)
										);

		}
	}

	//close FILE
	pclose(get_veths);


	//getting the highest device number
	gint highestDevID = atoi(getHighestDeviceID(device_numbers));

	//the new device id needs to be increased with one
	highestDevID++;
	//this will be the first new id (Y > max(X))
	gchar *newDevID_1 = g_strdup_printf("%d",highestDevID);
	//the second device id also needs to be increased with one
	highestDevID++;
	//this will be the second new id for the new peer dev (Y' > Y)
	gchar *newDevID_2 = g_strdup_printf("%d",highestDevID);

	//assembling command
	//ip link add uny_Y type veth peer name uny_Y'
	gchar *command = g_strconcat(
								"ip link add uny_",
								newDevID_1,
								" type veth peer name uny_",
								newDevID_2,
								NULL);
	//for executing the command
//	custom_log(INFO, g_strdup_printf("command:%s\n\n", command));
	int status = system(command);

	//command was successfully executed
	if(status == 0)
	{
		//if everything went fine (return value of the command is 0)
		custom_log(INFO, g_strdup_printf("A new veth pair has been created: "
								 "(uny_%s - uny_%s)",
								 newDevID_1,
								 newDevID_2));

		//we can free up gchar* command, since we do not require it anymore
		g_free(command);

		//concatenating the return value, e.g., uny_1-uny_2
		gchar* veth_pair_as_char = g_strconcat("uny_",
												newDevID_1,
												"-uny_",
												newDevID_2,
												NULL);
		return veth_pair_as_char;
	}

	else if(status == 2 || status == 512)
	{
		//return value of the command is 2 or 512 -> operation not permitted
		custom_log(ERROR, "Operation not permitted! You must be ROOT!");
		return NULL;
	}
	else
	{
		//other return values are not being examined, just 'throw' an error

		custom_log(ERROR, "An error occurred during creating veth pairs!\n"
				  "Operation may not permitted - You must be ROOT!");

		return NULL;
	}

}


/*
 *     ---------------------- SYSTEM -------------------------
 * This helper function will practically delete the veth pairs from the system
 * gchar* vnf_dev - vnf's device
 * gchar* sw_dev - switch's device
 */
void deleteVirtualEthernetPair(gchar* vnf_dev, gchar* sw_dev)
{

	//assembling the command
	//we do only need to delete one of the devices, since it irrevocably
	//deletes the other one as well
	gchar* command;
	command = g_strconcat(
						"ip link del ",
						vnf_dev,
						NULL);

	//execute the command
	int status = system(command);

	//check return value
	if(status == 0)
	{
		//Command was successfully executed
		custom_log(INFO, g_strdup_printf("Virtual ethernet pair [%s - %s] was "
								 "successfully deleted!",
								 vnf_dev,
								 sw_dev));
	}
	else if(status == 1 || status == 256)
	{
		//if device did not exist
		custom_log(ERROR, g_strdup_printf("Device %s not exists!",vnf_dev));
	}
	else if(status == 2 || status == 512)
	{
		//operation not permitted
		custom_log(ERROR, "Operation not permitted! You must be ROOT!");
	}
	else
	{
		//any further errors - other return values are not being examined,
		//just 'throw' an error
		custom_log(ERROR, g_strdup_printf("An error occurred during deleting "
								  "virtual ethernet pair [%s - %s]",
								  vnf_dev, sw_dev));
	}
}


/*
 * This procedure gets a certain switch port assigned to a device id
 * gchar* sw_id - id of the switch
 * gchar* dev_id - device id, which for the port is assigned
 * return gchar* - port number
 */
gchar* getSwitchPort(gchar* sw_id, gchar* dev_id)
{
	//first we need to get all the ports and the assigned device ids with our
	//helper function getAllSwitchPorts().
	//At the same time, we only read the corresponding port with a hashtable
	//lookup
	gchar* port = (gchar*)g_hash_table_lookup(getAllSwitchPorts(sw_id),dev_id);

	//check found port number
	if(port == NULL)
	{
		//Port number did not exists
		custom_log(ERROR, g_strdup_printf("%s is not connected to switch %s",
								  dev_id,
								  sw_id));
	}

	return port;

}


/*
 *     ---------------------- SYSTEM -------------------------
 * This function collects the ports and corresponding device ids of the given
 * switch
 * gchar* sw_id - id of the switch, e.g., s3
 * return GHashTable* - hashtable of the results ([port_num]=dev_id)
 */
GHashTable* getAllSwitchPorts(gchar* sw_id)
{
	//for storing all the device ids and the corresponding ports
	GHashTable *switch_ports_and_dev_ids =
			g_hash_table_new_full (g_str_hash, g_str_equal, g_free, g_free);

	//a line for stdout
	char path[100];

	//found ports and devices, e.g., 2(s3-eth2)
	gchar *ports_and_devices;

	//for running a command and reading its stdout
	FILE *get_ports_and_devices;

	//assembling the command
	//the corresponding line always consists of a mac address info, for instance
	//addr:46:be....., so we can grep 'addr' on the stdout.
	//The results will look like the following:
	//2(s3-eth2): addr:5a:42:6f:11:25:81
	//We can further use system calls for easing handling such as 'cut'
	gchar* command = g_strconcat(
								OVS_OFCTL_COMMAND,
								" show ",
								sw_id,
								"| grep addr|cut -d ':' -f 1",
								NULL);


	//run the command
	get_ports_and_devices = popen(command, "r");
	//This result, which must be parsed will look like this: 2(uny_X)

	//checking that command was run successfully
	if(get_ports_and_devices == NULL)
	{
		//error occurred during executing command
		custom_log(ERROR, g_strdup_printf("Failed to run command (%s)",command));

	}
	else
	{
		//command execution succeeded

		//reading stdout
		while(fgets(path,sizeof(path)-1, get_ports_and_devices) != NULL)
		{
			gchar* port;
			gchar* device_id;

			//tokenizing read line

			//this will produce '2' from '2(uny_X)'
			//this will produce 2
			ports_and_devices = strtok(path,"(");

			//duplicating variable
			port = g_strdup(ports_and_devices);

			//tokenize further
			//this will produce uny_X
			ports_and_devices = strtok(NULL,")");

			//storing uny_X in device_id
			device_id = g_strdup(ports_and_devices);

			//we need to remove the first whitespace character from port, so
			//here comes a trick with the tokenizer
			port = strtok(port," ");

//			g_print("port:%s\n", port);
//			g_print("dev_id:%s\n\n",device_id);

			//adding port and device ids to the hashtable
			add_string_element(switch_ports_and_dev_ids,
								g_strdup(device_id),
								g_strdup(port),
								TRUE);



		}
	}

	//close FILE
	pclose(get_ports_and_devices);
	//freeing gchar* command, since we do not need it anymore
	g_free(command);

	return switch_ports_and_dev_ids;
}




/*
 * This procedure gets the control port of the VNF
 * gchar* vnf_id - vnf id
 * return gchar* - control port
 */
gchar* getControlPort(gchar* vnf_id)
{
	//get the actual vnf data
	vnf_data *found_vnf = getVNF(vnf_id);

	//get control port
	return found_vnf->control_port;

}

/*
 * This procedure sets the control port
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * gchar *port - control port
 */
void setControlPort(gchar *vnf_id, gchar *port)
{
	//get the actual vnf data
	vnf_data *found_vnf = getVNF(vnf_id);

	//set control port
	found_vnf->control_port = port;
}


/*
 * This procedure gets the control ip of the VNF
 * gchar* vnf_id - vnf id
 * return gchar* - control IP
 */
gchar* getControlIP(gchar* vnf_id)
{
	//get the actual vnf data
	vnf_data *found_vnf = getVNF(vnf_id);

	//get control IP
	return found_vnf->control_ip;

}

/*
 * This procedure sets the control IP
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * gchar *ip_addr - control IP address
 */
void setControlIP(gchar *vnf_id, gchar *ip_addr)
{
	//get the actual vnf data
	vnf_data *found_vnf = getVNF(vnf_id);

	//set control port and IP
	found_vnf->control_ip = ip_addr;

}


/*
 *     ---------------------- DATASTRUCTURE -------------------------
 * This procedure removes a certain vnf with all its data from the hashtable
 * gchar *vnf_id - vnf id
 */
void removeVNF(gchar *vnf_id)
{
	//removing data from the hashtable of vnfs
	gboolean success = g_hash_table_remove(vnfs,vnf_id);

	//checking whether it was successful or not
	if(success)
	{
		//successfully deleted
		custom_log(INFO, "[VNF_DATASTRUCTURE] "
				 "VNF successfully removed!");
	}
	else
	{
		//could not been deleted
		custom_log(ERROR, "[VNF_DATASTRUCTURE] "
				  "VNF could not be removed!");
	}
}


/*
 * This procedure sets the click/vnf shell command
 * GHashTable *vnfs - hashtable of all the vnfs
 * gchar *vnf_id - vnf id
 * gchar *command - the linux shell command
 */
void setVNFCommand(gchar *vnf_id, gchar *command)
{
	//get the actual vnf data
	vnf_data *found_vnf = getVNF(vnf_id);

	//get vnf command
	found_vnf->vnf_command = command;
}


/*
 * This procedure gets the command of the vnf
 * gchar* vnf_id - the id of the vnf
 * return gchar* - the command
 */
gchar* getVNFCommand(gchar *vnf_id)
{
	//get the actual vnf data
	vnf_data *found_vnf = getVNF(vnf_id);

	return found_vnf->vnf_command;
}


/*
 * This procedure prints out the vnfs and their data
 */
void printVNFs(void)
{
	//printing with built-in foreach function that needs an other customized
	//function print_data to print information as we want
	g_hash_table_foreach(vnfs, (GHFunc) print_data, NULL);
}

/*
 * This function gets the vnfs' ids in a GList*
 * return GList* - the list of the vnfs' ids
 */
GList* getVNFIds(void)
{
	GList* list_of_vnfs_ids = g_hash_table_get_keys(vnfs);

	return list_of_vnfs_ids;
}

/*
 * This procedure returns the number of vnfs that are stored
 * return int - number of vnfs
 */
gint getNumberOfVNFs(void)
{
	//built-in function for getting the size of the hashtable vnfs
	return g_hash_table_size(vnfs);
}
