import { create } from 'zustand';
import { UI_VEHICLES_FILEID } from '@/constants/fileIds';

const defaultFleet = [
  {
    id: 1,
    name: 'Vehicle 1',
    capacity: 100,
    speed: 40,
    startTime: 0,
    endTime: 24,
    costPerDistance: 1,
    costPerTime: 0.5,
    fileId: UI_VEHICLES_FILEID,
  }
];

const useFleetStore = create((set) => ({
  fleet: defaultFleet,

  setFleet: (updatedFleet) => set({ fleet: updatedFleet }),

  addVehicle: (vehicle) =>
    set((state) => ({
      fleet: [...state.fleet, vehicle]
    })),

  updateVehicle: (index, field, value) =>
    set((state) => {
      const fleet = [...state.fleet];
      fleet[index] = {
        ...fleet[index],
        [field]: field === 'name' ? value : parseFloat(value)
      };
      return { fleet };
    }),

  removeVehicle: (index) =>
    set((state) => {
      const fleet = [...state.fleet];
      fleet.splice(index, 1);
      return { fleet };
    }),

  resetFleet: () => set({ fleet: defaultFleet })
}));

export default useFleetStore;
