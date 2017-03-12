#
# Build a 48K ROM
#
include $(BUILD_SYSTEM)/boot.mk
include $(BUILD_SYSTEM)/engine.mk

built_rom_ihx = $(LOCAL_BUILD_OUT_BIN)/$(LOCAL_ROM_NAME).ihx
built_rom_bin = $(LOCAL_BUILD_OUT_BIN)/$(LOCAL_ROM_NAME).bin
built_rom_48k = $(LOCAL_BUILD_OUT_ROM)/$(LOCAL_ROM_NAME).rom

all: $(built_rom_48k)

# Build local sourcess
#
BUILT_LOCAL_SRC_FILES := $(patsubst %.c, $(LOCAL_BUILD_OUT_BIN)/%.rel, $(LOCAL_SRC_FILES))

$(BUILT_LOCAL_SRC_FILES): $(LOCAL_BUILD_OUT_BIN)/%.rel: $(LOCAL_BUILD_SRC)/%.c
	$(hide) mkdir -p $(LOCAL_BUILD_OUT_BIN)
	$(hide) $(CROSS_CC) $(ENGINE_CFLAGS) -c -o $@ $^

# Build banked sources that are placed in page0
#
BUILT_LOCAL_BANKED_SRC_FILES := $(patsubst %.c, $(LOCAL_BUILD_OUT_BIN)/%.rel, $(LOCAL_BANKED_SRC_FILES))

$(BUILT_LOCAL_BANKED_SRC_FILES): $(LOCAL_BUILD_OUT_BIN)/%.rel: $(LOCAL_BUILD_SRC)/%.c
	$(hide) @mkdir -p $(LOCAL_BUILD_OUT_BIN)
	$(hide) $(CROSS_CC) $(ENGINE_CFLAGS) -bo 1 -c -o $@ $^

# Link with Engine and 48k bootstrap
#
$(built_rom_ihx) : $(BUILT_LOCAL_SRC_FILES) $(BUILT_LOCAL_BANKED_SRC_FILES) $(BUILT_ENGINE) $(BUILT_BOOTSTRAP_48K)
	@echo "-mwxuy" > $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	@echo "-i ${@}" >> $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	@echo "-b _CODE_1=0x10000" >> $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	@echo "-b _BOOT=0x4000" >> $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	@echo "-b _CODE=0x40D8" >> $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	@echo "-b _HOME=0xB000" >> $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	@echo "-b _DATA=0xC000" >> $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	@echo "-l z80" >> $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	@echo $^ | tr ' ' '\n' >> $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	@echo "-e" >> $(LOCAL_BUILD_OUT_BIN)/rom48.lnk
	$(hide) sdldgb -k $(SDCC_LIB) -f $(LOCAL_BUILD_OUT_BIN)/rom48.lnk

$(built_rom_bin) : $(built_rom_ihx) | $(HEX2BIN)
	$(hide) cd $(LOCAL_BUILD_OUT_BIN) && $(HEX2BIN) -e bin $(notdir $^)

# Generate the actual ROM
#
$(built_rom_48k) : $(built_rom_bin)
	$(hide) mkdir -p $(LOCAL_BUILD_OUT_ROM)
	$(hide) tr "\000" "\377" < /dev/zero | dd ibs=1k count=48 of=$@
	$(hide)dd if=$^ of=$@ conv=notrunc