
interface CityEntity {
  city: string;
  id: number
  sources: CitySource[];
}

interface CitySource {
  source: string;
  displaySource: string;
}