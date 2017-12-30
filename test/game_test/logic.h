#ifndef _LOGIC_H_
#define _LOGIC_H_


struct game_state_t {
	uint8_t map_x;	// position on the map in tile coordinates
	uint8_t map_y;
	uint8_t cross_cnt;
	uint8_t live_cnt;

	/* action item status */
	uint8_t hearth[9];
	uint8_t scroll[7];
	uint8_t cross[12];
	bool bell;
	uint8_t invisible_trigger[5];
	uint8_t checkpoint[8];
	uint8_t toggle[3];
	bool cross_switch;
	bool cross_switch_enable;
	bool door_trigger;
};

extern struct game_state_t game_state;

void pickup_heart(struct displ_object *dpo, uint8_t data);
void pickup_scroll(struct displ_object *dpo, uint8_t data);
void pickup_cross(struct displ_object *dpo, uint8_t data);
void checkpoint_handler(struct displ_object *dpo, uint8_t data);
void toggle_handler(struct displ_object *dpo, uint8_t data);
void bell_handler(struct displ_object *dpo, uint8_t data);
void crosswitch_handler(struct displ_object *dpo, uint8_t data);
// void set_trigger_handler_object(struct map_object_item *map_object);
void trigger_handler(struct displ_object *dpo, uint8_t data);
#endif