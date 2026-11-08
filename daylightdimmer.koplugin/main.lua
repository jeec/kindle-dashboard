-- Daytime-only frontlight dimmer for KOReader.
-- Uses the same saved solar location as AutoWarmth.

local Device = require("device")
local UIManager = require("ui/uimanager")
local WidgetContainer = require("ui/widget/container/widgetcontainer")
local SunTime = require("suntime")

local Powerd = Device.powerd

if not Device:hasFrontlight() then
    return { disabled = true }
end

local DaylightDimmer = WidgetContainer:extend{
    name = "daylightdimmer",
    idle_minutes = 5,
    dimmed_by_plugin = false,
    solar_key = nil,
    sunrise = nil,
    sunset = nil,
}

function DaylightDimmer:init()
    self.enabled = G_reader_settings:nilOrTrue("daylight_dimmer_enabled")
    self.idle_minutes = G_reader_settings:readSetting("daylight_dimmer_idle_minutes", 5)
    self.ui.menu:registerToMainMenu(self)
    UIManager.event_hook:registerWidget("InputEvent", self)
    self.onSuspend = self._onSuspend
    self.onResume = self._onResume
end

function DaylightDimmer:isDaylight()
    -- Keep the solar location and timezone in sync with AutoWarmth, but only
    -- recalculate when the date or saved location changes (e.g. not per page turn).
    local location = G_reader_settings:readSetting("autowarmth_location", "")
    local latitude = G_reader_settings:readSetting("autowarmth_latitude", 64.31)
    local longitude = G_reader_settings:readSetting("autowarmth_longitude", -20.30)
    local timezone = SunTime:getTimezoneOffset()
    local altitude = G_reader_settings:readSetting("autowarmth_altitude", 200)
    local key = table.concat({os.date("%Y-%m-%d"), location, latitude, longitude, timezone, altitude}, ":")

    if key ~= self.solar_key then
        self.solar_key = key
        self.sunrise = nil
        self.sunset = nil
        local ok = pcall(function()
            SunTime:setPosition(location, latitude, longitude, timezone, altitude, true)
            SunTime:setAdvanced()
            SunTime:setDate()
            SunTime:calculateTimes()
            self.sunrise = SunTime.times and SunTime.times[5]
            self.sunset = SunTime.times and SunTime.times[7]
        end)
        if not ok then return false end
    end

    if not self.sunrise or not self.sunset then return false end

    local now_seconds = SunTime:getTimeInSec()
    return now_seconds >= self.sunrise * 3600 and now_seconds < self.sunset * 3600
end

function DaylightDimmer:scheduleDim()
    UIManager:unschedule(self.dimIfDaylight)
    if self.enabled then
        UIManager:scheduleIn(self.idle_minutes * 60, self.dimIfDaylight, self)
    end
end

function DaylightDimmer:onInputEvent()
    if not self.enabled then return end

    -- During daytime, any touch can bring the frontlight back after this
    -- plugin dimmed it or AutoWarmth switched it off at sunrise.
    if self:isDaylight() and Powerd:isFrontlightOff() then
        Powerd:turnOnFrontlight()
        self.dimmed_by_plugin = false
    end

    self:scheduleDim()
end

function DaylightDimmer:dimIfDaylight()
    if not self.enabled or not self:isDaylight() then return end
    if Powerd:isFrontlightOff() then return end

    self.dimmed_by_plugin = true
    Powerd:turnOffFrontlight()
end

function DaylightDimmer:_onSuspend()
    UIManager:unschedule(self.dimIfDaylight)
end

function DaylightDimmer:_onResume()
    -- Start a fresh idle interval after waking; never dim immediately on resume.
    self:scheduleDim()
end

function DaylightDimmer:addToMainMenu(menu_items)
    menu_items.daylightdimmer = {
        text = "Daytime frontlight dimmer",
        checked_func = function() return self.enabled end,
        callback = function(touchmenu_instance)
            self.enabled = not self.enabled
            G_reader_settings:saveSetting("daylight_dimmer_enabled", self.enabled)
            UIManager:unschedule(self.dimIfDaylight)
            if self.enabled then self:scheduleDim() end
            if touchmenu_instance then touchmenu_instance:updateItems() end
        end,
    }
end

return DaylightDimmer
